// Custom search UI for suche.html (search.py writes the markup, this fills it): entity resolution first, from the
// suche.json the build writes (docs/plan.md 11.7, D20), then full-text hits in speeches from the Pagefind JS API.
// German UI, see docs/plan.md. Pure, DOM-free helpers are exported at the bottom for tests; everything else only
// runs in a browser with a #search element, so requiring this file in Node is side-effect-free.
'use strict';

const PAGE_SIZE = 10;
const CAP = 8; // filter values shown before "N weitere"
const GROUPS = ['Art', 'Fraktion', 'Thema', 'Monat', 'Person'];
const LABELS = { Art: 'Art', Fraktion: 'Fraktion', Thema: 'Thema', Monat: 'Monat', Person: 'Person' };

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

// Pagefind excerpts are plain text with the matches already wrapped in <mark>…</mark>: escape everything else,
// keep the marks (dropped tags stay html-safe either way).
function markSafe(html) {
  return String(html ?? '').split(/(<mark>.*?<\/mark>)/gs)
    .map(part => part.startsWith('<mark>') ? `<mark>${esc(part.slice(6, -7))}</mark>` : esc(part)).join('');
}

// ------------------------------------------------------------------ entities

const ENTITY_CAP = 6; // entities shown per type before "N weitere"

// lower case, no diacritics, "ß" as "ss": "Thüringen" and "thuringen" meet, as do "Straße" and "strasse"
function norm(s) {
  return String(s ?? '').toLowerCase().replace(/ß/g, 'ss').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

// The entities matching every word of the query, grouped by type in the index's order, each group best first: the
// label equal to the query, then starting with it, then with a word starting with it, then any match (ties keep the
// index's order). index is suche.json: {types, items: [[type, label, sub, href, keys], …]}.
function resolve(index, q, cap = ENTITY_CAP) {
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const query = words.join(' ');
  const groups = index.types.map(type => ({ type, total: 0, items: [] }));
  index.items.forEach(([t, label, sub, href, keys], i) => {
    const l = norm(label), hay = `${l} ${norm(sub)} ${norm(keys)}`;
    if (!words.every(w => hay.includes(w))) return;
    const rank = l === query ? 0 : l.startsWith(query) ? 1 : words.every(w => (' ' + l).includes(' ' + w)) ? 2 : 3;
    groups[t].items.push({ label, sub, href, rank, i });
  });
  for (const g of groups) {
    g.items.sort((a, b) => a.rank - b.rank || a.i - b.i);
    g.total = g.items.length;
    g.items = g.items.slice(0, cap).map(({ label, sub, href }) => ({ label, sub, href }));
  }
  return groups.filter(g => g.total);
}

// the heading of each entity type, the anchor it is jumped to by (#e-person …) and the site's colour tokens
const SINGULAR = { Person: 'Person', Gruppe: 'Fraktion oder Gremium', Ort: 'Ort', Vorgang: 'Vorgang',
  Sachgebiet: 'Sachgebiet', Thema: 'Thema', Sitzungswoche: 'Sitzungswoche' };
const PLURAL = { Person: 'Personen', Gruppe: 'Fraktionen und Gremien', Ort: 'Orte', Vorgang: 'Vorgänge',
  Sachgebiet: 'Sachgebiete', Thema: 'Themen', Sitzungswoche: 'Sitzungswochen' };
const TOKEN = { 'CDU/CSU': 'cdu', SPD: 'spd', AfD: 'afd', 'BÜNDNIS 90/DIE GRÜNEN': 'gru', 'Die Linke': 'lin',
  fraktionslos: 'frl', Bundesregierung: 'reg' };
// a Vorgang's DIP status in the colours of the phase pills (design.css .php, procedures.STATUS_STAGE)
const STAGE = { 'Noch nicht beraten': 'eingebracht', 'Überwiesen': 'ausschuesse', 'Beschlussempfehlung liegt vor':
  'ausschuesse', Angenommen: 'beschlossen', Verabschiedet: 'beschlossen', 'Verkündet': 'verkuendet',
  Abgelehnt: 'abgelehnt', 'Zustimmung versagt': 'versagt' };
const SHOWN = 6; // rows per type before "Alle N zeigen"

function anchor(type) { return `e-${norm(type)}`; }

function entityRow(type, x) {
  let sub = esc(x.sub), dot = '';
  if (type === 'Person' && TOKEN[x.sub]) dot = `<span class="dot" style="--c:var(--${TOKEN[x.sub]})"></span>`;
  if (type === 'Gruppe' && TOKEN[x.label]) dot = `<span class="dot" style="--c:var(--${TOKEN[x.label]})"></span>`;
  if (type === 'Vorgang') {
    const [kind, status] = x.sub.split(' · ');
    if (status) sub = `${esc(kind)} <span class="php${STAGE[status] ? ` st-${STAGE[status]}` : ''}">${esc(status)}</span>`;
  }
  return `<a class="row sent" href="${esc(x.href)}"><span class="t"><span class="ti">${dot}${esc(x.label)}</span>` +
    `<span class="sub">${sub}</span></span></a>`;
}

// One card per type; `open` holds the types shown in full (up to the cap resolve() was called with).
function entitiesHtml(groups, open = new Set()) {
  return groups.map(g => {
    const shown = open.has(g.type) ? g.items : g.items.slice(0, SHOWN);
    const rest = g.total - shown.length;
    const more = shown.length < g.items.length
      ? `<button type="button" class="s-all" data-t="${esc(g.type)}">Alle ${g.items.length < g.total ? `${g.items.length} von ` : ''}${g.total} zeigen</button>`
      : rest > 0 ? `<p class="faint">und ${rest} weitere: genauer suchen</p>` : '';
    return `<section class="s-ent${g.type === 'Vorgang' ? ' wide' : ''}" id="${anchor(g.type)}">` +
      `<h3>${esc(PLURAL[g.type] || g.type)} <span class="n">${g.total.toLocaleString('de-DE')}</span></h3>` +
      `<div class="rows">${shown.map(x => entityRow(g.type, x)).join('')}</div>${more}</section>`;
  }).join('');
}

// The pills in the head: one per type found, then the speeches, each a jump to its section.
function jumpHtml(groups, speeches) {
  const pill = (href, k, label) => `<a class="utag" href="#${href}"><b>${k.toLocaleString('de-DE')}</b> ${esc(label)}</a>`;
  return groups.map(g => pill(anchor(g.type), g.total, (g.total === 1 ? SINGULAR : PLURAL)[g.type] || g.type)).join('') +
    (speeches ? pill('reden', speeches, speeches === 1 ? 'Rede' : 'Reden') : '');
}

// ------------------------------------------------------------------ speeches (Pagefind)

function formatDate(iso) {
  return iso && iso.length >= 10 ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : '';
}

// One result row, styled like the rest of the site's .rows/.row (votes, sittings): `d` is what result.data() gives.
function resultRow(d) {
  const art = d.filters?.Art?.[0] || '';
  const date = formatDate(d.meta?.date);
  const title = esc(d.meta?.title || d.url);
  return `<a class="row sres" href="${esc(d.url)}"><span class="d">${esc(date)}</span>` +
    `<span class="t"><span class="ti">${title}</span><span class="sub">${markSafe(d.excerpt)}</span></span>` +
    `<span class="l">${art ? `<span class="tag">${esc(art)}</span>` : ''}</span></a>`;
}

// The query string for a deep link: ?q=… plus one entry per checked filter value ("OR within a group" mirrors
// the search itself). checked is {group: Set<string>}.
function queryString(q, checked) {
  const h = new URLSearchParams();
  if (q) h.set('q', q);
  for (const g of GROUPS) for (const v of checked[g] || []) h.append(g, v);
  return h.toString();
}

// The values of one filter group, sorted by their live count descending (ties alphabetically): `total` is the
// group's full value set (from pagefind.filters(), so a value can be listed even at zero), `live` the counts for
// the current query and the other active filters (from a search result's `filters`).
function sortValues(total, live) {
  return Object.keys(total).sort((a, b) => (live[b] || 0) - (live[a] || 0) || a.localeCompare(b, 'de'));
}

// the groups folded at first (their heading stays, with the number of values chosen)
const FOLDED = ['Thema', 'Monat', 'Person'];

// The HTML of one filter group panel; `shut` folds it to its heading.
function filterGroupHtml(group, total, live, checked, open, shut = false) {
  const values = sortValues(total, live || {});
  const shown = open ? values : values.slice(0, CAP);
  const rows = shown.map(v => {
    const c = (live || {})[v] || 0, on = checked.has(v);
    const dot = group === 'Fraktion' ? `<span class="dot" style="--c:var(--${TOKEN[v] || 'reg'})"></span>` : '';
    return `<label class="sf-item${!c && !on ? ' zero' : ''}"><input type="checkbox" data-g="${esc(group)}" ` +
      `value="${esc(v)}"${on ? ' checked' : ''}><span class="sf-name">${dot}${esc(v)}</span>` +
      `<span class="sf-n">${c.toLocaleString('de-DE')}</span></label>`;
  }).join('');
  const more = values.length > CAP
    ? `<button type="button" class="sf-more" data-g="${esc(group)}">${open ? 'weniger' : `${values.length - CAP} weitere`}</button>`
    : '';
  const chosen = checked.size ? `<span class="sf-on">${checked.size} gewählt</span>` : '';
  return `<div class="sf-group${shut ? ' shut' : ''}"><h3><button type="button" class="sf-h" data-g="${esc(group)}" ` +
    `aria-expanded="${!shut}">${esc(LABELS[group] || group)}${chosen}<span class="sf-chev" aria-hidden="true"></span>` +
    `</button></h3>${shut ? '' : `<div class="sf-list${open ? ' expanded' : ''}">${rows}</div>${more}`}</div>`;
}

async function boot() {
  const $ = id => document.getElementById(id);
  const n = x => x.toLocaleString('de-DE');
  const els = {
    input: $('sq'), toggle: $('sf-toggle'), filters: $('sf-panel'), count: $('s-count'),
    results: $('s-results'), more: $('s-more'), entities: $('s-entities'), jump: $('s-jump'), ex: $('s-ex'),
    n: $('s-n'),
  };
  let INDEX = null, GROUPS_FOUND = [], SPEECHES = 0;
  const openTypes = new Set();
  const renderJump = () => {
    const q = els.input.value.trim();
    els.jump.innerHTML = q ? jumpHtml(GROUPS_FOUND, SPEECHES) : '';
    els.jump.hidden = !els.jump.innerHTML;
    els.ex.hidden = !!q;
  };
  const renderEntities = () => {
    if (!INDEX) return;
    GROUPS_FOUND = resolve(INDEX, els.input.value, 60);
    els.entities.innerHTML = GROUPS_FOUND.length ? entitiesHtml(GROUPS_FOUND, openTypes)
      : (els.input.value.trim() ? '<p class="explain s-none">Keine Person, kein Ort, Gremium, Vorgang, Sachgebiet, Thema und keine Sitzungswoche mit diesem Namen.</p>' : '');
    renderJump();
  };
  els.entities.onclick = ev => {
    const b = ev.target.closest('.s-all');
    if (b) { openTypes.add(b.dataset.t); renderEntities(); }
  };
  const entitiesReady = fetch('suche.json').then(r => r.json()).then(x => { INDEX = x; renderEntities(); })
    .catch(() => { els.entities.innerHTML = ''; });

  const state = { checked: {}, open: {}, shut: {}, master: {}, results: [], shown: 0 };

  function activeFilters() {
    const f = {};
    for (const g of GROUPS) if (state.checked[g]?.size) f[g] = [...state.checked[g]];
    return f;
  }

  function syncUrl() {
    const qs = queryString(els.input.value, state.checked);
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  }

  function renderFilters(live) {
    els.filters.innerHTML = GROUPS.filter(g => state.master[g])
      .map(g => filterGroupHtml(g, state.master[g], live?.[g], state.checked[g] || new Set(), !!state.open[g],
        !!state.shut[g]))
      .join('');
    els.filters.querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.onchange = () => {
        const g = cb.dataset.g;
        const set = state.checked[g] || (state.checked[g] = new Set());
        set[cb.checked ? 'add' : 'delete'](cb.value);
        run(false);
      };
    });
    els.filters.querySelectorAll('.sf-more').forEach(btn => {
      btn.onclick = () => { state.open[btn.dataset.g] = !state.open[btn.dataset.g]; renderFilters(live); };
    });
    els.filters.querySelectorAll('.sf-h').forEach(btn => {
      btn.onclick = () => { state.shut[btn.dataset.g] = !state.shut[btn.dataset.g]; renderFilters(live); };
    });
  }

  async function renderResults() {
    const slice = state.results.slice(0, state.shown);
    const data = slice.length ? await Promise.all(slice.map(r => r.data())) : [];
    els.results.innerHTML = data.map(resultRow).join('');
    els.results.hidden = !data.length;
    els.more.hidden = state.shown >= state.results.length;
  }

  async function run(debounced) {
    const q = els.input.value.trim();
    const opts = { filters: activeFilters() };
    const res = debounced ? await pagefind.debouncedSearch(q || null, opts, 200) : await pagefind.search(q || null, opts);
    if (res === null) return; // superseded by a newer keystroke
    state.results = res.results;
    state.shown = Math.min(PAGE_SIZE, state.results.length);
    SPEECHES = state.results.length;
    els.n.textContent = n(SPEECHES);
    els.n.hidden = false;
    const active = Object.values(state.checked).some(s => s.size);
    els.count.textContent = SPEECHES
      ? `${q ? `Treffer für „${q}“` : 'Alle Reden'}${active ? ' mit den gewählten Filtern' : ''}${q ? ', die passendsten zuerst' : ''}.`
      : (q ? `Keine Rede enthält „${q}“${active ? ' mit den gewählten Filtern' : ''}.` : 'Keine Rede mit den gewählten Filtern.');
    renderJump();
    renderFilters(res.filters);
    await renderResults();
    syncUrl();
  }

  els.input.oninput = () => { openTypes.clear(); renderEntities(); run(true); };
  els.more.onclick = () => { state.shown = Math.min(state.shown + PAGE_SIZE, state.results.length); renderResults(); };
  // on a wide screen the whole column folds away and the hits take the width; the choice is kept for the next visit
  const side = $('sf-side'), layout = document.querySelector('.s-layout');
  const setSide = hide => {
    layout.classList.toggle('nofilter', hide);
    side.textContent = hide ? 'Filter zeigen' : 'Filter ausblenden';
    side.setAttribute('aria-expanded', String(!hide));
  };
  let hidden = false;
  try { hidden = localStorage.getItem('suche-filter') === 'aus'; } catch (e) { /* private mode */ }
  setSide(hidden);
  side.onclick = () => {
    const hide = !layout.classList.contains('nofilter');
    setSide(hide);
    try { localStorage.setItem('suche-filter', hide ? 'aus' : 'an'); } catch (e) { /* private mode */ }
  };
  if (els.toggle) {
    els.toggle.onclick = () => {
      const open = els.filters.classList.toggle('open');
      els.toggle.setAttribute('aria-expanded', String(open));
    };
  }

  const params = new URLSearchParams(location.search);
  els.input.value = params.get('q') || '';
  for (const g of GROUPS) {
    const vs = params.getAll(g);
    if (vs.length) state.checked[g] = new Set(vs);
    state.shut[g] = FOLDED.includes(g) && !vs.length;
  }

  await entitiesReady;
  const pagefind = await import('./pagefind/pagefind.js');
  await pagefind.options({ highlightParam: 'hl' });
  state.master = await pagefind.filters();
  window.pagefind = pagefind; // for debugging in the console only

  // idle state (no query, no filter checked): show the filters with their site-wide counts, but skip an expensive
  // unfiltered "browse everything" search until the visitor actually asks for one
  if (els.input.value || Object.values(state.checked).some(s => s.size)) {
    await run(false);
  } else {
    renderFilters(state.master);
    els.count.textContent = 'Die Treffer erscheinen, sobald du suchst oder einen Filter wählst.';
  }
}

if (typeof document !== 'undefined' && document.getElementById('search')) {
  boot();
}

// the top bar's search field (nav.js) ranks its suggestions with the same resolve()
if (typeof window !== 'undefined') window.cardsSearch = { resolve, norm };

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { esc, markSafe, formatDate, resultRow, queryString, sortValues, filterGroupHtml, norm, resolve,
    entitiesHtml, jumpHtml };
}
