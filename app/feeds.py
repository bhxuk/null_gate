"""Live feeds fetched by the server: weather (Open-Meteo, no key) and GitHub repositories.

Results are cached so a dashboard left open on several screens does not hammer
the upstream services. Everything degrades to a readable error message.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from urllib.parse import quote, urlencode, urlsplit

WEATHER_TTL = 10 * 60
GITHUB_TTL = 30 * 60


class FeedError(Exception):
    """Upstream problem, safe to show to the user."""


class Cache:
    def __init__(self):
        self.lock = threading.Lock()
        self.items = {}

    def get(self, key, ttl, fetch):
        with self.lock:
            hit = self.items.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        try:
            value = fetch()
        except FeedError:
            if hit:  # serve slightly stale data rather than an error
                return hit[1]
            raise
        with self.lock:
            self.items[key] = (time.time(), value)
        return value


def get_json(url, headers=None, timeout=10):
    request = urllib.request.Request(url, headers={'User-Agent': 'null_gate (bhxuk.com)', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(4 * 1024 * 1024))
    except urllib.error.HTTPError as exc:
        raise FeedError(f'{urlsplit(url).hostname} returned HTTP {exc.code}') from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FeedError(f'Could not reach {urlsplit(url).hostname} ({getattr(exc, "reason", exc)})') from None


class Feeds:
    def __init__(self, token_source=None):
        self.cache = Cache()
        self.token_source = token_source or (lambda: '')

    # ---- weather -------------------------------------------------------
    def weather(self, place):
        lat, lon = round(float(place['lat']), 3), round(float(place['lon']), 3)

        def fetch():
            query = urlencode({
                'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 6,
                'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,'
                           'wind_speed_10m,precipitation',
                'hourly': 'temperature_2m,weather_code,precipitation_probability,is_day',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max',
                'wind_speed_unit': 'mph',
            })
            data = get_json('https://api.open-meteo.com/v1/forecast?' + query)
            current, hourly, daily = data.get('current') or {}, data.get('hourly') or {}, data.get('daily') or {}
            now = current.get('time', '')
            times = hourly.get('time') or []
            start = next((i for i, t in enumerate(times) if t >= now[:13]), 0)
            hours = [{'time': times[i], 'temp': hourly['temperature_2m'][i], 'code': hourly['weather_code'][i],
                      'rain': (hourly.get('precipitation_probability') or [None] * len(times))[i],
                      'day': hourly.get('is_day', [1] * len(times))[i]}
                     for i in range(start, min(start + 12, len(times)))]
            days = [{'date': d, 'code': daily['weather_code'][i], 'max': daily['temperature_2m_max'][i],
                     'min': daily['temperature_2m_min'][i], 'rain': (daily.get('precipitation_probability_max') or [None] * 9)[i],
                     'sunrise': daily['sunrise'][i], 'sunset': daily['sunset'][i]}
                    for i, d in enumerate(daily.get('time') or [])]
            return {'place': place.get('name', ''), 'timezone': data.get('timezone', ''), 'current': {
                'temp': current.get('temperature_2m'), 'feels': current.get('apparent_temperature'),
                'humidity': current.get('relative_humidity_2m'), 'code': current.get('weather_code', 0),
                'day': current.get('is_day', 1), 'wind': current.get('wind_speed_10m'),
                'precipitation': current.get('precipitation'), 'time': now},
                'hours': hours, 'days': days, 'updated': time.time()}
        return self.cache.get(('weather', lat, lon), WEATHER_TTL, fetch)

    def find_place(self, name):
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            raise ValueError('Type a town or city name')
        data = get_json('https://geocoding-api.open-meteo.com/v1/search?' +
                        urlencode({'name': name.strip(), 'count': 6, 'language': 'en', 'format': 'json'}))
        return {'results': [{'name': r.get('name', ''), 'region': ', '.join(x for x in (r.get('admin1'), r.get('country')) if x),
                             'lat': r['latitude'], 'lon': r['longitude']}
                            for r in data.get('results') or [] if 'latitude' in r]}

    # ---- GitHub --------------------------------------------------------
    def _github(self, path):
        headers = {'Accept': 'application/vnd.github+json'}
        token = self.token_source()
        if token:
            headers['Authorization'] = 'Bearer ' + token  # higher rate limit
        return get_json('https://api.github.com' + path, headers)

    @staticmethod
    def _repo(r):
        return {'name': r.get('name', ''), 'full': r.get('full_name', ''), 'url': r.get('html_url', ''),
                'description': (r.get('description') or '')[:200], 'language': r.get('language') or '',
                'stars': r.get('stargazers_count', 0), 'forks': r.get('forks_count', 0),
                'created': r.get('created_at', ''), 'pushed': r.get('pushed_at', ''),
                'owner': (r.get('owner') or {}).get('login', ''), 'private': bool(r.get('private'))}

    def github(self, user):
        def mine():
            repos = self._github(f'/users/{quote(user)}/repos?sort=created&direction=desc&per_page=12')
            return [self._repo(r) for r in repos if isinstance(r, dict)]

        def trending():
            since = (date.today() - timedelta(days=7)).isoformat()
            data = self._github('/search/repositories?' + urlencode(
                {'q': f'created:>{since}', 'sort': 'stars', 'order': 'desc', 'per_page': 12}))
            return [self._repo(r) for r in data.get('items') or []]

        out = {'user': user, 'mine': [], 'trending': [], 'errors': []}
        for key, fetch in (('mine', mine), ('trending', trending)):
            try:
                out[key] = self.cache.get(('github', key, user if key == 'mine' else ''), GITHUB_TTL, fetch)
            except FeedError as exc:
                out['errors'].append(str(exc))
        return out
