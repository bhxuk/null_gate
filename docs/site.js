// null_gate website: screen tour, copy button and latest release label.

const SHOTS = {
  overview: ['Overview', 'Your start page. Every block is a tile you can move, resize or hide.',
    ['Live clock with six themes and world clocks', 'Weather with an animated sky and forecast', 'Smart home status chips and quick lights', 'Favourites and every category as tiles']],
  links: ['Links', 'Everything you saved, grouped by category. Compact cards fit a lot on one screen.',
    ['Search with / and add with n', 'Drag links between categories or onto Favourites', 'Switch to cards, table or TV with one click', 'Bulk import bookmarks, CSV, .url and .webloc files']],
  tv: ['TV launcher', 'Wide tiles in shelves, made for a TV or a wall screen.',
    ['Arrow keys move between tiles, Enter opens', 'Your preview images become tile artwork', 'Fullscreen button for a clean launcher']],
  home: ['Smart home', 'Rooms, devices and cameras from Home Assistant in one place.',
    ['One-tap room lights', 'Lights, speakers, thermostats, plugs and scenes', 'Camera snapshots and a full-screen live view', 'Star a device to pin it to your overview']],
  light: ['Light theme', 'The same dashboard in daylight. Pick from six accent colours and three backgrounds.',
    ['Dark and light themes', 'Settings are shared across every device', 'Choice saved on your server']],
  mobile: ['Phone', 'Fully responsive, so the dashboard works on your phone too.',
    ['Slide-out sidebar', 'Touch-friendly controls', 'Same data on every device']],
};

const img = document.getElementById('tourImg');
const frame = img.closest('.window');
function show(key) {
  const [title, text, list] = SHOTS[key];
  document.querySelectorAll('[data-shot]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.shot === key)));
  img.style.opacity = '0';
  const next = new Image();
  next.onload = () => {
    img.src = next.src; img.width = next.naturalWidth; img.height = next.naturalHeight;
    img.alt = `null_gate ${title} screen`; img.style.opacity = '1';
  };
  next.src = `img/${key}.jpg`;
  frame.classList.toggle('phone', key === 'mobile');
  document.getElementById('tourTitle').textContent = title;
  document.getElementById('tourText').textContent = text;
  document.getElementById('tourList').replaceChildren(...list.map(t => Object.assign(document.createElement('li'), { textContent: t })));
}
document.querySelectorAll('[data-shot]').forEach(b => b.addEventListener('click', () => show(b.dataset.shot)));
show('overview');

document.getElementById('copyInstall').addEventListener('click', async e => {
  try {
    await navigator.clipboard.writeText(document.getElementById('installCommands').textContent);
    e.target.textContent = 'Copied ✓';
  } catch { e.target.textContent = 'Select and copy'; }
  setTimeout(() => { e.target.textContent = 'Copy commands'; }, 1800);
});

fetch('https://api.github.com/repos/bhxuk/null_gate/releases/latest')
  .then(r => r.ok ? r.json() : null)
  .then(r => { if (r?.tag_name) document.getElementById('releaseLink').textContent = `${r.tag_name} ↗`; })
  .catch(() => {});
