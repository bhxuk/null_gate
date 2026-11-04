// Customisable overview: every block is a tile on a 12-column grid that you can
// move (drag the handle) and resize (drag the corner) in Customise mode.
// The layout is saved in dashboard.json as `widgets: [{id, w, h, hidden}]`.

import { app, commit, render } from './state.js';
import { h, toast } from './util.js';

const COLS = 12;
const ROW = 40;   // px per grid row
const GAP = 16;   // px, must match .tiles gap in CSS

export let editing = false;
export const setEditing = value => { editing = value; render(); };

/**
 * Merge the saved layout with the available tiles. New tiles (a new category,
 * say) are appended with their default size; tiles that no longer exist are dropped.
 */
export function resolveLayout(defs) {
  const saved = app.state.widgets || [];
  const known = new Set(defs.map(d => d.id));
  const out = saved.filter(w => known.has(w.id)).map(w => ({ ...w }));
  const have = new Set(out.map(w => w.id));
  for (const d of defs) if (!have.has(d.id)) out.push({ id: d.id, w: d.w, h: d.h, hidden: false });
  return out;
}

function save(layout, message) {
  return commit(s => { s.widgets = layout.map(({ id, w, h, hidden }) => ({ id, w, h, hidden: !!hidden })); }, message);
}

let draggedTile = null;

/** Build the tile grid. `defs` = [{ id, title, w, h, build: () => Node|null }]. */
export function tileGrid(defs) {
  const byId = new Map(defs.map(d => [d.id, d]));
  const layout = resolveLayout(defs);
  const visible = layout.filter(t => !t.hidden);
  const hidden = layout.filter(t => t.hidden);

  const bar = h('div', { class: 'tiles-bar' + (editing ? ' editing' : '') },
    editing ? [
      h('span', { class: 'hint' }, 'Drag ⠿ to move a tile, drag the ◢ corner to resize it, ✕ to hide it.'),
      h('span', { class: 'spacer' }),
      hidden.length ? h('select', { class: 'add-tile', 'aria-label': 'Add a hidden tile', onchange: e => {
        const t = layout.find(x => x.id === e.target.value);
        if (t) { t.hidden = false; save(layout, `${byId.get(t.id).title} added`); }
      } }, h('option', { value: '' }, `+ Add tile (${hidden.length})`), hidden.map(t => h('option', { value: t.id }, byId.get(t.id).title))) : null,
      h('button', { class: 'btn small', onclick: () => commit(s => { s.widgets = []; }, 'Layout reset') }, 'Reset'),
      h('button', { class: 'btn small primary', onclick: () => setEditing(false) }, 'Done'),
    ] : h('button', { class: 'btn small customise', onclick: () => setEditing(true) }, '✎ Customise'));

  const grid = h('div', { class: 'tiles' + (editing ? ' editing' : '') });
  for (const t of visible) {
    const def = byId.get(t.id);
    const content = def.build();
    if (!content && !editing) continue;
    const tile = h('section', { class: 'tile tile-' + t.id.replace(/[^a-z0-9]/gi, '-'), dataset: { tile: t.id },
      style: { gridColumn: `span ${Math.min(t.w, COLS)}`, gridRow: `span ${t.h}` } },
      editing ? h('div', { class: 'tile-chrome' },
        h('span', { class: 'tile-handle', draggable: 'true', title: 'Drag to move', 'aria-label': `Move ${def.title}` }, '⠿'),
        h('b', {}, def.title),
        h('span', { class: 'tile-size' }, `${t.w}×${t.h}`),
        h('button', { class: 'iconbtn small', title: 'Hide tile', 'aria-label': `Hide ${def.title}`, onclick: () => { t.hidden = true; save(layout, `${def.title} hidden`); } }, '✕')) : null,
      h('div', { class: 'tile-body' }, content || h('p', { class: 'dim pad' }, 'Nothing to show yet.')),
      editing ? h('span', { class: 'tile-resize', title: 'Drag to resize', 'aria-hidden': 'true' }) : null);
    if (editing) wireTile(tile, t, layout, grid);
    grid.append(tile);
  }
  if (!editing) requestAnimationFrame(() => markOverflow(grid));
  return h('div', { class: 'tiles-wrap' }, bar, grid);
}

/** Show a soft fade at the bottom of tiles whose content scrolls. */
function markOverflow(grid) {
  grid.querySelectorAll('.tile-body').forEach(body => {
    const check = () => body.parentElement.classList.toggle('more', body.scrollHeight - body.scrollTop - body.clientHeight > 4);
    check();
    body.addEventListener('scroll', check, { passive: true });
  });
}

function wireTile(tile, t, layout, grid) {
  const handle = tile.querySelector('.tile-handle');
  handle.addEventListener('dragstart', e => {
    draggedTile = t.id;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', t.id);
    e.dataTransfer.setDragImage(tile, 20, 20);
    requestAnimationFrame(() => tile.classList.add('dragging'));
  });
  handle.addEventListener('dragend', () => {
    draggedTile = null;
    tile.classList.remove('dragging');
    grid.querySelectorAll('.tile-drop').forEach(x => x.classList.remove('tile-drop'));
  });
  tile.addEventListener('dragover', e => {
    if (!draggedTile || draggedTile === t.id) return;
    e.preventDefault();
    tile.classList.add('tile-drop');
  });
  tile.addEventListener('dragleave', e => { if (!tile.contains(e.relatedTarget)) tile.classList.remove('tile-drop'); });
  tile.addEventListener('drop', e => {
    if (!draggedTile) return;
    e.preventDefault();
    const from = layout.findIndex(x => x.id === draggedTile);
    const [moving] = layout.splice(from, 1);
    layout.splice(layout.findIndex(x => x.id === t.id), 0, moving);
    draggedTile = null;
    save(layout);
  });

  // Resize by dragging the corner, snapping to grid columns and rows.
  const corner = tile.querySelector('.tile-resize');
  corner.addEventListener('pointerdown', e => {
    e.preventDefault();
    corner.setPointerCapture(e.pointerId);
    const colWidth = (grid.clientWidth - GAP * (COLS - 1)) / COLS;
    const start = { x: e.clientX, y: e.clientY, w: tile.offsetWidth, h: tile.offsetHeight };
    const size = { w: t.w, h: t.h };
    tile.classList.add('resizing');
    const move = ev => {
      size.w = Math.max(2, Math.min(COLS, Math.round((start.w + ev.clientX - start.x + GAP) / (colWidth + GAP))));
      size.h = Math.max(2, Math.min(30, Math.round((start.h + ev.clientY - start.y + GAP) / (ROW + GAP))));
      tile.style.gridColumn = `span ${size.w}`;
      tile.style.gridRow = `span ${size.h}`;
      tile.querySelector('.tile-size').textContent = `${size.w}×${size.h}`;
    };
    const up = () => {
      corner.removeEventListener('pointermove', move);
      corner.removeEventListener('pointerup', up);
      tile.classList.remove('resizing');
      if (size.w !== t.w || size.h !== t.h) { t.w = size.w; t.h = size.h; save(layout); }
    };
    corner.addEventListener('pointermove', move);
    corner.addEventListener('pointerup', up);
  });
}

export { toast };
