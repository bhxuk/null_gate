// Overview widgets: greeting, animated clock, live weather and a daily quote.

import { api } from './api.js';
import { app, commit } from './state.js';
import { h, clear } from './util.js';

// ------------------------------------------------------------------ clock

function parts(zone, seconds, hour12 = false) {
  const now = new Date();
  const fmt = new Intl.DateTimeFormat('en-GB', { timeZone: zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12 });
  const bits = Object.fromEntries(fmt.formatToParts(now).map(p => [p.type, p.value]));
  const [hh, mm, ss] = now.toLocaleTimeString('en-GB', { timeZone: zone, hour12: false }).split(':').map(Number);
  const hm = `${bits.hour}:${bits.minute}`;
  return {
    hm, sec: bits.second, period: hour12 ? (bits.dayPeriod || (hh < 12 ? 'am' : 'pm')).toUpperCase() : '',
    time: seconds ? `${hm}:${bits.second}` : hm,
    date: now.toLocaleDateString('en-GB', { timeZone: zone, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
    hour: hh % 24, minute: mm, second: ss,
  };
}

/** Minutes the zone is ahead of the main clock's zone. */
function offsetFrom(zone, base) {
  const at = z => {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: z, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric' })
      .formatToParts(new Date()).map(x => [x.type, x.value]));
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
  };
  return Math.round((at(zone) - at(base)) / 60000);
}

const offsetLabel = mins => {
  if (!mins) return 'Same time';
  const h = Math.trunc(Math.abs(mins) / 60), m = Math.abs(mins) % 60;
  return `${mins > 0 ? '+' : '−'}${h}h${m ? ` ${m}m` : ''}`;
};

export function greeting(zone) {
  const { hour } = parts(zone);
  return hour < 5 ? 'Good night' : hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

const city = zone => zone === 'UTC' ? 'UTC' : zone.split('/').pop().replace(/_/g, ' ');
const hour12 = () => app.state.settings.clock24 === false;

/** Each character in its own span so changed digits can roll in. */
function digits(text) {
  return [...text].map(ch => h('span', { class: ch === ':' ? 'colon' : 'digit' }, ch));
}

function updateDigits(el, text) {
  const chars = [...text];
  if (el.children.length !== chars.length) { clear(el, digits(text)); return; }
  chars.forEach((ch, i) => {
    const span = el.children[i];
    if (span.textContent !== ch) {
      const fresh = h('span', { class: (ch === ':' ? 'colon' : 'digit') + ' roll' }, ch);
      span.replaceWith(fresh);
    }
  });
}

function daylight() {
  const today = weatherData()?.days?.[0];
  if (!today?.sunrise || !today?.sunset) return null;
  const rise = Date.parse(today.sunrise), set = Date.parse(today.sunset);
  // Open-Meteo times are local to the place; compare in the same frame.
  const nowLocal = Date.parse(weatherData().current.time || '') || rise;
  const progress = Math.min(1, Math.max(0, (nowLocal - rise) / (set - rise)));
  const length = Math.round((set - rise) / 60000);
  return { rise: today.sunrise.slice(11, 16), set: today.sunset.slice(11, 16), progress, length: `${Math.floor(length / 60)}h ${length % 60}m` };
}

const themeName = v => (CLOCK_THEMES.find(([k]) => k === v) || [, 'Neon'])[1];
export const CLOCK_THEMES = [['neon', 'Neon'], ['minimal', 'Minimal'], ['widget', 'Widget'], ['retro', 'Retro LED'], ['flip', 'Flip'], ['analog', 'Analog']];
const SVG = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}) => {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
};

function analogFace() {
  const face = svg('svg', { viewBox: '0 0 100 100', class: 'analog', 'aria-hidden': 'true' });
  face.append(svg('circle', { cx: 50, cy: 50, r: 48, class: 'face' }));
  for (let i = 0; i < 60; i++) {
    const major = i % 5 === 0;
    face.append(svg('line', { x1: 50, y1: major ? 6 : 4.5, x2: 50, y2: major ? 12 : 7.5, class: major ? 'tick major' : 'tick', transform: `rotate(${i * 6} 50 50)` }));
  }
  [12, 3, 6, 9].forEach((n, i) => {
    const a = i * Math.PI / 2;
    const t = svg('text', { x: 50 + Math.sin(a) * 33, y: 50 - Math.cos(a) * 33 + 4, class: 'num', 'text-anchor': 'middle' });
    t.textContent = n;
    face.append(t);
  });
  face.append(svg('line', { x1: 50, y1: 54, x2: 50, y2: 26, class: 'hand hour', id: 'handHour' }));
  face.append(svg('line', { x1: 50, y1: 56, x2: 50, y2: 14, class: 'hand minute', id: 'handMinute' }));
  face.append(svg('line', { x1: 50, y1: 60, x2: 50, y2: 9, class: 'hand second', id: 'handSecond' }));
  face.append(svg('circle', { cx: 50, cy: 50, r: 2.6, class: 'pin' }));
  return face;
}

export function clockPanel() {
  const { timezone, clocks } = app.state.settings;
  const theme = app.state.settings.clockTheme || 'neon';
  const p = parts(timezone, true, hour12());
  const sun = daylight();
  const card = h('section', { class: `clock-card ct-${theme}`, id: 'clockCard' },
    h('div', { class: 'clock-top' },
      h('span', { class: 'clock-zone', title: timezone }, '◷ ' + clockPlace(timezone).toUpperCase()),
      h('span', { class: 'live-chip' }, h('i'), 'LIVE'),
      h('span', { class: 'spacer' }),
      h('button', { class: 'iconbtn small theme-btn', title: `Clock theme: ${themeName(theme)} (click for next)`, 'aria-label': 'Next clock theme',
        onclick: () => {
          const i = CLOCK_THEMES.findIndex(([v]) => v === theme);
          const [next, label] = CLOCK_THEMES[(i + 1) % CLOCK_THEMES.length];
          commit(st => { st.settings.clockTheme = next; }, `Clock theme: ${label}`);
        } }, '🎨'),
      h('div', { class: 'segmented mini', role: 'group', 'aria-label': 'Clock format' },
        h('button', { class: hour12() ? 'active' : '', onclick: () => setFormat(false) }, '12h'),
        h('button', { class: hour12() ? '' : 'active', onclick: () => setFormat(true) }, '24h')),
      h('button', { class: 'iconbtn small', title: 'Fullscreen clock', 'aria-label': 'Fullscreen clock', onclick: () => fullscreen(card) }, '⛶')),
    theme === 'analog' ? analogFace() : null,
    h('div', { class: 'big-time' },
      h('span', { class: 'hm', id: 'clockHM' }, digits(p.hm)),
      h('span', { class: 'sec-col' },
        h('span', { class: 'sec', id: 'clockSec' }, digits(p.sec)),
        h('span', { class: 'period', id: 'clockPeriod' }, p.period))),
    h('div', { class: 'sec-bar' }, h('i', { id: 'secBar' })),
    h('div', { class: 'clock-date', id: 'clockDate' }, p.date),
    sun ? h('div', { class: 'daylight' },
      h('span', {}, '☀ ' + sun.rise),
      h('span', { class: 'day-track' }, h('i', { style: { '--p': sun.progress } })),
      h('span', {}, sun.set + ' ☾'),
      h('span', { class: 'dim' }, sun.length + ' daylight')) : null,
    h('div', { class: 'world-cards' }, clocks.map(zone => {
      const w = parts(zone, false, hour12());
      const day = w.hour >= 7 && w.hour < 19;
      return h('div', { class: 'world-card' + (day ? ' is-day' : ' is-night') },
        h('div', { class: 'wc-head' }, h('b', {}, city(zone)), h('span', {}, offsetLabel(offsetFrom(zone, timezone)))),
        h('div', { class: 'wc-time' }, h('strong', { dataset: { zone } }, w.hm), h('small', {}, (day ? '☀ Day' : '☾ Night'))));
    })));
  return card;
}

/** The weather town when it shares the clock's time zone (e.g. Birmingham), otherwise the zone's city. */
function clockPlace(timezone) {
  const place = app.state.settings.weather?.name;
  const w = weatherData();
  if (place && (!w || !w.timezone || w.timezone === timezone)) return place;
  return city(timezone);
}

function setFormat(is24) {
  commit(s => { s.settings.clock24 = is24; });
}

function fullscreen(el) {
  if (document.fullscreenElement) document.exitFullscreen();
  else el.requestFullscreen?.().catch(() => {});
}

/** Smooth seconds bar: every animation frame while the clock is on screen. */
function animate() {
  const bar = document.getElementById('secBar');
  if (bar) {
    const now = new Date();
    bar.style.transform = `scaleX(${(now.getSeconds() + now.getMilliseconds() / 1000) / 60})`;
  }
  const second = document.getElementById('handSecond');
  if (second && app.state) {
    const p = parts(app.state.settings.timezone);
    const sec = p.second + new Date().getMilliseconds() / 1000;
    second.setAttribute('transform', `rotate(${sec * 6} 50 50)`);
    document.getElementById('handMinute').setAttribute('transform', `rotate(${(p.minute + sec / 60) * 6} 50 50)`);
    document.getElementById('handHour').setAttribute('transform', `rotate(${((p.hour % 12) + p.minute / 60) * 30} 50 50)`);
  }
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

export function tickClocks() {
  if (!app.state) return;
  const hm = document.getElementById('clockHM');
  if (hm) {
    const p = parts(app.state.settings.timezone, true, hour12());
    updateDigits(hm, p.hm);
    updateDigits(document.getElementById('clockSec'), p.sec);
    document.getElementById('clockPeriod').textContent = p.period;
    document.getElementById('clockDate').textContent = p.date;
  }
  document.querySelectorAll('[data-zone]').forEach(el => { el.textContent = parts(el.dataset.zone, false, hour12()).hm; });
}

// ---------------------------------------------------------------- weather

// WMO weather codes → [label, scene]
const CODES = {
  0: ['Clear sky', 'clear'], 1: ['Mainly clear', 'clear'], 2: ['Partly cloudy', 'partly'], 3: ['Overcast', 'cloudy'],
  45: ['Fog', 'fog'], 48: ['Freezing fog', 'fog'],
  51: ['Light drizzle', 'drizzle'], 53: ['Drizzle', 'drizzle'], 55: ['Heavy drizzle', 'drizzle'], 56: ['Freezing drizzle', 'drizzle'], 57: ['Freezing drizzle', 'drizzle'],
  61: ['Light rain', 'rain'], 63: ['Rain', 'rain'], 65: ['Heavy rain', 'rain'], 66: ['Freezing rain', 'rain'], 67: ['Freezing rain', 'rain'],
  71: ['Light snow', 'snow'], 73: ['Snow', 'snow'], 75: ['Heavy snow', 'snow'], 77: ['Snow grains', 'snow'],
  80: ['Light showers', 'rain'], 81: ['Showers', 'rain'], 82: ['Violent showers', 'rain'], 85: ['Snow showers', 'snow'], 86: ['Heavy snow showers', 'snow'],
  95: ['Thunderstorm', 'storm'], 96: ['Thunderstorm with hail', 'storm'], 99: ['Thunderstorm with hail', 'storm'],
};
const condition = code => CODES[code] || ['Weather', 'cloudy'];
const ICON = { clear: ['☀', '☾'], partly: ['⛅', '☁'], cloudy: ['☁', '☁'], fog: ['🌫', '🌫'], drizzle: ['🌦', '🌧'], rain: ['🌧', '🌧'], snow: ['❄', '❄'], storm: ['⛈', '⛈'] };
const icon = (code, day = 1) => ICON[condition(code)[1]][day ? 0 : 1];
const round = v => (v === null || v === undefined ? '–' : Math.round(v));

let weather = null;
export const weatherData = () => weather;
let weatherError = '';
let weatherAt = 0;

export async function loadWeather(force = false) {
  if (!force && weather && Date.now() - weatherAt < 10 * 60 * 1000) return;
  try {
    weather = await api('weather');
    weatherError = '';
  } catch (error) {
    weatherError = error.message;
  }
  weatherAt = Date.now();
  const el = document.getElementById('weather');
  if (el) el.replaceWith(weatherPanel());
  const clock = document.getElementById('clockCard');
  if (clock && !document.fullscreenElement) clock.replaceWith(clockPanel());
}

/** Inline "change location" form inside the weather card. */
function placePicker() {
  const results = h('div', { class: 'place-results' });
  const input = h('input', { name: 'q', placeholder: 'Town or city', 'aria-label': 'Weather location', maxlength: 80, autocomplete: 'off' });
  const form = h('form', { class: 'place-picker', onsubmit: async e => {
    e.preventDefault();
    const q = input.value.trim();
    if (q.length < 2) return;
    clear(results, h('p', { class: 'hint' }, 'Searching…'));
    try {
      const { results: found } = await api('weather/search?q=' + encodeURIComponent(q));
      clear(results, found.length ? found.map(r => h('button', { type: 'button', class: 'place', onclick: async () => {
        await commit(st => { st.settings.weather = { name: r.name, lat: r.lat, lon: r.lon }; }, `Weather set to ${r.name}`);
        weather = null;
        loadWeather(true);
      } }, h('b', {}, r.name), h('span', {}, r.region))) : h('p', { class: 'hint' }, 'No places found. Try a nearby town.'));
    } catch (error) { clear(results, h('p', { class: 'hint' }, error.message)); }
  } },
    h('div', { class: 'inline-form' }, input, h('button', { class: 'btn small primary' }, 'Find'),
      h('button', { type: 'button', class: 'btn small', onclick: () => form.remove() }, 'Cancel')),
    results);
  setTimeout(() => input.focus(), 0);
  return form;
}

function placeButton(name) {
  return h('button', { class: 'place-btn', title: 'Change location', onclick: e => {
    const body = e.target.closest('.weather').querySelector('.weather-body');
    if (!body.querySelector('.place-picker')) body.prepend(placePicker());
  } }, '◍ ' + (name || 'Weather').toUpperCase() + ' ✎');
}

/** An animated scene: sun, moon and stars, drifting clouds, rain, snow, fog or lightning. */
function scene(kind, day) {
  const layer = (cls, n = 0) => h('div', { class: cls }, Array.from({ length: n }, (_, i) => h('i', { style: { '--i': i, '--x': `${(i * 37) % 100}%`, '--y': `${(i * 23) % 70}%`, '--d': `${(i * 0.23) % 1.6}s` } })));
  const sky = h('div', { class: `sky sky-${kind} ${day ? 'day' : 'night'}`, 'aria-hidden': 'true' });
  if (!day) sky.append(layer('stars', 18));
  if (['clear', 'partly'].includes(kind)) sky.append(day ? h('div', { class: 'sun' }, h('span', { class: 'rays' })) : h('div', { class: 'moon' }));
  if (kind !== 'clear') sky.append(layer('clouds', kind === 'partly' ? 2 : 4));
  if (kind === 'fog') sky.append(layer('fog', 4));
  if (['drizzle', 'rain', 'storm'].includes(kind)) sky.append(layer('rain', kind === 'drizzle' ? 16 : 34));
  if (kind === 'snow') sky.append(layer('snow', 26));
  if (kind === 'storm') sky.append(h('div', { class: 'flash' }));
  return sky;
}

export function weatherPanel() {
  if (!weather) {
    return h('section', { class: 'weather panel-block', id: 'weather' },
      h('div', { class: 'weather-body' }, placeButton(app.state.settings.weather?.name), h('p', { class: 'dim' }, weatherError || 'Loading the weather…'),
        weatherError ? h('button', { class: 'btn small', onclick: () => loadWeather(true) }, 'Try again') : null));
  }
  const c = weather.current;
  const [label, kind] = condition(c.code);
  const today = weather.days[0] || {};
  const time = t => t ? t.slice(11, 16) : '–';
  return h('section', { class: `weather panel-block w-${kind} ${c.day ? 'day' : 'night'}`, id: 'weather' },
    scene(kind, c.day),
    h('div', { class: 'weather-body' },
      h('div', { class: 'weather-now' },
        h('div', {},
          placeButton(weather.place),
          h('div', { class: 'weather-temp' }, `${round(c.temp)}°`),
          h('div', { class: 'weather-label' }, label)),
        h('dl', { class: 'weather-facts' },
          h('div', {}, h('dt', {}, 'Feels like'), h('dd', {}, `${round(c.feels)}°`)),
          h('div', {}, h('dt', {}, 'High / low'), h('dd', {}, `${round(today.max)}° / ${round(today.min)}°`)),
          h('div', {}, h('dt', {}, 'Humidity'), h('dd', {}, `${round(c.humidity)}%`)),
          h('div', {}, h('dt', {}, 'Wind'), h('dd', {}, `${round(c.wind)} mph`)),
          h('div', {}, h('dt', {}, 'Sunrise'), h('dd', {}, time(today.sunrise))),
          h('div', {}, h('dt', {}, 'Sunset'), h('dd', {}, time(today.sunset))))),
      h('div', { class: 'hours' }, weather.hours.map((hr, i) => h('div', { class: 'hour' },
        h('span', {}, i === 0 ? 'Now' : hr.time.slice(11, 16)), h('b', {}, icon(hr.code, hr.day)), h('strong', {}, `${round(hr.temp)}°`),
        hr.rain ? h('small', {}, `${hr.rain}%`) : h('small', {}, ' ')))),
      h('div', { class: 'days' }, weather.days.slice(0, 6).map((d, i) => h('div', { class: 'day' },
        h('span', {}, i === 0 ? 'Today' : new Date(d.date + 'T12:00').toLocaleDateString('en-GB', { weekday: 'short' })),
        h('b', {}, icon(d.code)), h('strong', {}, `${round(d.max)}°`), h('small', {}, `${round(d.min)}°`))))));
}

// ------------------------------------------------------------------ quotes

const QUOTES = [
  ['The best way to get started is to quit talking and begin doing.', 'Walt Disney'],
  ['Simplicity is the ultimate sophistication.', 'Leonardo da Vinci'],
  ['It always seems impossible until it’s done.', 'Nelson Mandela'],
  ['Make it work, make it right, make it fast.', 'Kent Beck'],
  ['The secret of getting ahead is getting started.', 'Mark Twain'],
  ['Well done is better than well said.', 'Benjamin Franklin'],
  ['Do what you can, with what you have, where you are.', 'Theodore Roosevelt'],
  ['First, solve the problem. Then, write the code.', 'John Johnson'],
  ['You miss 100% of the shots you don’t take.', 'Wayne Gretzky'],
  ['Quality is not an act, it is a habit.', 'Aristotle'],
  ['Stay hungry, stay foolish.', 'Stewart Brand'],
  ['The future depends on what you do today.', 'Mahatma Gandhi'],
  ['Small deeds done are better than great deeds planned.', 'Peter Marshall'],
  ['Action is the foundational key to all success.', 'Pablo Picasso'],
  ['Talk is cheap. Show me the code.', 'Linus Torvalds'],
  ['Everything you’ve ever wanted is on the other side of fear.', 'George Addair'],
  ['If you can dream it, you can do it.', 'Walt Disney'],
  ['A year from now you may wish you had started today.', 'Karen Lamb'],
  ['Done is better than perfect.', 'Sheryl Sandberg'],
  ['The only way to do great work is to love what you do.', 'Steve Jobs'],
  ['Discipline is choosing between what you want now and what you want most.', 'Abraham Lincoln (attributed)'],
  ['Programs must be written for people to read, and only incidentally for machines to execute.', 'Harold Abelson'],
  ['Believe you can and you’re halfway there.', 'Theodore Roosevelt'],
  ['Opportunities don’t happen. You create them.', 'Chris Grosser'],
  ['What we think, we become.', 'Buddha'],
  ['Great things are done by a series of small things brought together.', 'Vincent van Gogh'],
  ['The man who moves a mountain begins by carrying away small stones.', 'Confucius'],
  ['Don’t watch the clock; do what it does. Keep going.', 'Sam Levenson'],
  ['Any sufficiently advanced technology is indistinguishable from magic.', 'Arthur C. Clarke'],
  ['Learn as if you will live forever, live like you will die tomorrow.', 'Mahatma Gandhi'],
  ['Success is not final, failure is not fatal: it is the courage to continue that counts.', 'Winston Churchill'],
  ['Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away.', 'Antoine de Saint-Exupéry'],
  ['The best time to plant a tree was 20 years ago. The second best time is now.', 'Chinese proverb'],
  ['Hard work beats talent when talent doesn’t work hard.', 'Tim Notke'],
  ['It does not matter how slowly you go as long as you do not stop.', 'Confucius'],
  ['Creativity is intelligence having fun.', 'Albert Einstein (attributed)'],
  ['The way to get started is to stop planning and start doing.', 'Unknown'],
  ['Be so good they can’t ignore you.', 'Steve Martin'],
  ['Little by little, one travels far.', 'J. R. R. Tolkien'],
  ['Keep your face always toward the sunshine, and shadows will fall behind you.', 'Walt Whitman'],
  ['Every expert was once a beginner.', 'Helen Hayes'],
  ['Turn your wounds into wisdom.', 'Oprah Winfrey'],
  ['The harder I work, the luckier I get.', 'Samuel Goldwyn'],
  ['Act as if what you do makes a difference. It does.', 'William James'],
  ['Make each day your masterpiece.', 'John Wooden'],
  ['Start where you are. Use what you have. Do what you can.', 'Arthur Ashe'],
  ['Your time is limited, so don’t waste it living someone else’s life.', 'Steve Jobs'],
  ['In the middle of every difficulty lies opportunity.', 'Albert Einstein (attributed)'],
  ['Measure twice, cut once.', 'Proverb'],
  ['Fortune favours the bold.', 'Virgil'],
];

export function quoteOfTheDay(offset = 0) {
  const now = new Date();
  const day = Math.floor((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(now.getFullYear(), 0, 0)) / 86400000);
  return QUOTES[(day + now.getFullYear() * 7 + offset + QUOTES.length * 10) % QUOTES.length];
}

let quoteOffset = 0;
export function quotePanel() {
  const [text, author] = quoteOfTheDay(quoteOffset);
  const panel = h('section', { class: 'quote panel-block', id: 'quote' },
    h('div', { class: 'block-head' }, h('h2', {}, '❝ Quote of the day'),
      h('button', { class: 'iconbtn small', title: 'Another quote', 'aria-label': 'Show another quote', onclick: () => {
        quoteOffset++;
        const next = quotePanel();
        next.classList.add('fade');
        panel.replaceWith(next);
      } }, '↻')),
    h('blockquote', {}, h('p', {}, text), h('cite', {}, '— ' + author)));
  return panel;
}

export { clear };
