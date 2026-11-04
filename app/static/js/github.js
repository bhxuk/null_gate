// GitHub: your newest repositories and what is trending worldwide this week.

import { api } from './api.js';
import { app, commit } from './state.js';
import { h, ago, toast } from './util.js';

let data = null;
let loadedAt = 0;
let loading = null;

const LANG_COLOURS = { JavaScript: '#f1e05a', TypeScript: '#3178c6', Python: '#3572a5', Go: '#00add8', Rust: '#dea584', Shell: '#89e051',
  HTML: '#e34c26', CSS: '#663399', Java: '#b07219', 'C++': '#f34b7d', C: '#555555', 'C#': '#178600', PHP: '#4f5d95', Ruby: '#701516',
  Swift: '#f05138', Kotlin: '#a97bff', Dart: '#00b4ab', Vue: '#41b883', Svelte: '#ff3e00', Lua: '#000080', Dockerfile: '#384d54' };

export function loadGithub(force = false) {
  if (!force && data && Date.now() - loadedAt < 15 * 60 * 1000) return Promise.resolve(data);
  loading ??= api('github').then(result => {
    data = result;
    loadedAt = Date.now();
    document.querySelectorAll('[data-github]').forEach(el => el.replaceWith(el.dataset.github === 'view' ? githubView() : githubStrip()));
    return data;
  }).catch(error => { toast(error.message, 'error'); }).finally(() => { loading = null; });
  return loading;
}

const k = n => n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : String(n);
const time = iso => iso ? ago(Date.parse(iso)) : '';

function repoCard(r, { showOwner = false } = {}) {
  return h('a', { class: 'repo', href: r.url, target: '_blank', rel: 'noopener noreferrer' },
    h('div', { class: 'repo-head' },
      h('b', {}, showOwner ? r.full : r.name),
      r.private ? h('span', { class: 'tag' }, 'Private') : null),
    h('p', {}, r.description || h('span', { class: 'dim' }, 'No description')),
    h('div', { class: 'repo-meta' },
      r.language ? h('span', {}, h('i', { class: 'lang', style: { background: LANG_COLOURS[r.language] || 'var(--dim)' } }), r.language) : null,
      h('span', {}, '★ ' + k(r.stars)),
      r.forks ? h('span', {}, '⑂ ' + k(r.forks)) : null,
      h('span', { class: 'dim' }, 'Created ' + time(r.created))));
}

function errors() {
  return data?.errors?.length ? h('div', { class: 'notice bad' }, data.errors.join(' · ')) : null;
}

export function githubView() {
  const user = app.state.settings.githubUser;
  if (!data) loadGithub();
  const head = h('div', { class: 'view-head' },
    h('div', {}, h('div', { class: 'eyebrow' }, 'GITHUB'), h('h1', {}, 'Repositories'),
      h('p', { class: 'dim' }, data ? `Updated ${new Date(loadedAt).toLocaleTimeString('en-GB')}` : 'Loading from GitHub…')),
    h('div', { class: 'row' },
      h('form', { class: 'inline-form', onsubmit: e => {
        e.preventDefault();
        const name = e.target.user.value.trim();
        if (name === user) return;
        commit(s => { s.settings.githubUser = name; }, name ? `Showing repositories by ${name}` : 'GitHub user cleared').then(() => loadGithub(true));
      } }, h('input', { name: 'user', value: user, placeholder: 'GitHub username', 'aria-label': 'GitHub username', maxlength: 39 }), h('button', { class: 'btn' }, 'Show')),
      h('button', { class: 'btn', onclick: () => loadGithub(true) }, '↻ Refresh'),
      user ? h('a', { class: 'btn', href: `https://github.com/${user}`, target: '_blank', rel: 'noopener noreferrer' }, 'Profile ↗') : null));
  return h('section', { class: 'view', dataset: { github: 'view' } }, head, errors(),
    h('div', { class: 'github-columns' },
      h('section', { class: 'panel-block' },
        h('div', { class: 'block-head' }, h('h2', {}, `◆ Newest by ${user || '…'}`), h('span', { class: 'hint' }, 'Most recently created')),
        data ? (data.mine.length ? h('div', { class: 'repo-list' }, data.mine.map(r => repoCard(r))) : h('p', { class: 'dim' }, 'No public repositories found.')) : h('p', { class: 'dim' }, 'Loading…')),
      h('section', { class: 'panel-block' },
        h('div', { class: 'block-head' }, h('h2', {}, '🔥 Trending worldwide'), h('span', { class: 'hint' }, 'Most-starred new repos this week')),
        data ? h('div', { class: 'repo-list' }, data.trending.map(r => repoCard(r, { showOwner: true }))) : h('p', { class: 'dim' }, 'Loading…'))),
    h('p', { class: 'hint' }, 'GitHub only shows public repositories here. Trending lists repositories created in the last 7 days, sorted by stars.'));
}

/** Compact strip for the overview: your four newest repos and the top four trending. */
export function githubStrip() {
  if (!app.state.settings.githubUser) return null;
  if (!data) loadGithub();
  return h('section', { class: 'panel-block', dataset: { github: 'strip' } },
    h('div', { class: 'block-head' }, h('h2', {}, '◆ GitHub'), h('a', { href: '#github', class: 'dim' }, 'All repositories →')),
    errors(),
    !data ? h('p', { class: 'dim' }, 'Loading from GitHub…') : h('div', { class: 'github-columns' },
      h('div', {}, h('h3', { class: 'sub' }, 'Your newest'), h('div', { class: 'repo-list compact' }, data.mine.slice(0, 4).map(r => repoCard(r)))),
      h('div', {}, h('h3', { class: 'sub' }, 'Trending this week'), h('div', { class: 'repo-list compact' }, data.trending.slice(0, 4).map(r => repoCard(r, { showOwner: true }))))));
}
