// The search field at the left end of the top bar (ui.site_header, docs/plan.md 12.1). Without JavaScript it is a
// plain form: Enter goes to suche.html?q=…. With it, typing shows suggestions from suche-kurz.json (the entity
// index without the Gemeinden, search.py), grouped by type and ranked by search.js's resolve(), so the bar and the
// search page find the same entities in the same order. The index and search.js are fetched on the first keystroke,
// never on page load. On narrow screens the field is an icon that opens it over the bar.
'use strict';
(() => {
  const form = document.querySelector('header .nav-q');
  if (!form) return;
  const root = form.dataset.root || '';
  const input = form.querySelector('input');
  const box = form.querySelector('.nav-sug');
  const icon = form.querySelector('.nav-qi');
  const header = form.closest('header');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const narrow = matchMedia('(max-width: 1240px)');
  let index = null, loading = null, links = [], hi = -1;

  function lib() {
    if (window.cardsSearch) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.type = 'module';  // a module: its helpers do not collide with a page's own globals
      s.src = `${root}search.js`;
      s.onload = resolve;
      s.onerror = reject;
      document.head.append(s);
    });
  }

  function load() {
    loading ??= Promise.all([fetch(`${root}suche-kurz.json`).then(r => r.ok ? r.json() : null), lib()])
      .then(([idx]) => { index = idx; })
      .catch(() => { index = null; });
    return loading;
  }

  function close() { box.hidden = true; links = []; hi = -1; }

  function render() {
    const q = input.value.trim();
    if (q.length < 2 || !index || !window.cardsSearch) { close(); return; }
    const groups = window.cardsSearch.resolve(index, q, 4);
    const all = `<a class="all" href="${root}suche.html?q=${encodeURIComponent(q)}">Alle Treffer für „${esc(q)}“, auch in Reden →</a>`;
    box.innerHTML = groups.map(g => `<div class="g">${esc(g.type)}</div>` + g.items.map(x =>
      `<a href="${root}${esc(x.href)}">${esc(x.label)}<span class="s">${esc(x.sub)}</span></a>`).join('')).join('') + all;
    box.hidden = false;
    links = [...box.querySelectorAll('a')];
    hi = -1;
  }

  input.addEventListener('input', () => { if (input.value.trim().length >= 2) load().then(render); else close(); });
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') { close(); if (narrow.matches) toggle(false); return; }
    if (box.hidden || !links.length) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      hi = Math.max(0, Math.min(links.length - 1, hi + (e.key === 'ArrowDown' ? 1 : -1)));
      links.forEach((a, i) => a.classList.toggle('hi', i === hi));
      links[hi].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && hi >= 0) {
      e.preventDefault();
      location.href = links[hi].href;
    }
  });
  // an empty field leads to the search page itself, with its examples and filters
  form.addEventListener('submit', e => { if (!input.value.trim()) { e.preventDefault(); location.href = `${root}suche.html`; } });

  function toggle(open) {
    header.classList.toggle('q-open', open);
    icon.setAttribute('aria-expanded', open);
    if (open) input.focus(); else close();
  }
  icon.addEventListener('click', () => narrow.matches ? toggle(!header.classList.contains('q-open')) : input.focus());

  // the phone's menu (shell.css, max-width 760px): "Menü" folds the sections out below the bar and back
  const menu = header.querySelector('.nav-menu');
  function fold(open) {
    header.classList.toggle('menu-open', open);
    menu.setAttribute('aria-expanded', open);
    menu.textContent = open ? 'Schließen' : 'Menü';
  }
  if (menu) {
    menu.addEventListener('click', e => { e.stopPropagation(); fold(!header.classList.contains('menu-open')); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && header.classList.contains('menu-open')) { fold(false); menu.focus(); } });
  }
  document.addEventListener('click', e => {
    if (menu && header.classList.contains('menu-open') && !header.contains(e.target)) fold(false);
    if (form.contains(e.target)) return;
    close();
    if (narrow.matches && header.classList.contains('q-open')) toggle(false);
  });
})();

// The design language (design.css): on Research pages, an explanation that follows a heading (p.explain) moves into an
// info button at the end of the heading, as on the Radar; without JavaScript it stays where it is. Pages that draw
// their tabs later (card.js) are watched. The info button: hover or focus shows it, a click pins it.
(() => {
  if (window.__info) return;
  window.__info = true;
  const research = !document.body.classList.contains('mode-radar');
  const HEADS = 'H1, H2, H3';
  const isEx = el => el && el.matches('p.explain');
  const infoFor = h => {
    let i = h.querySelector(':scope > .info');
    if (!i) {
      i = document.createElement('span');
      i.className = 'info';
      i.innerHTML = '<button type="button" class="info-b" aria-expanded="false" aria-label="Erklärung">i</button><span class="info-t" role="tooltip"></span>';
      h.appendChild(i);
    }
    return i.lastChild;
  };
  const move = (t, html) => t.appendChild(Object.assign(document.createElement('p'), { innerHTML: html }));
  // a long lead keeps its first sentence as the page's subtitle; the rest goes behind the button
  const firstSentence = html => { const m = html.match(/^(.{60,260}?[^\d\s][.!?])\s+(?=[A-ZÄÖÜ„])/s); return m ? [m[1], html.slice(m[0].length)] : [html, '']; };
  const convertAfter = h => {
    let q = h.nextElementSibling;
    if (q && q.matches('p.lead') && q.textContent.length > 260) {
      const [keep, rest] = firstSentence(q.innerHTML);
      if (rest) { q.innerHTML = keep; move(infoFor(h), rest); }
      q = q.nextElementSibling;
    } else if (q && q.matches('p.lead')) q = q.nextElementSibling;
    let end = q, run = [];
    while (isEx(end)) { run.push(end); end = end.nextElementSibling; }
    // an explanation that is the section's only content (nothing after it) stays as text: it is the answer itself
    if (!run.length || !end) return;
    const t = infoFor(h);
    run.forEach(p => { move(t, p.innerHTML); p.remove(); });
  };
  const convertBefore = p => {  // an explanation right before a heading (a tab's text above its list) goes with it
    if (!p.isConnected || !isEx(p)) return;
    let end = p; while (isEx(end.nextElementSibling)) end = end.nextElementSibling;
    const h = end.nextElementSibling;
    if (!h || !h.matches(HEADS)) return;
    const t = infoFor(h), run = [];
    for (let q = p; q !== h; q = q.nextElementSibling) run.push(q);
    run.forEach(q => { move(t, q.innerHTML); q.remove(); });
  };
  const sweep = root => {
    root.querySelectorAll(HEADS).forEach(h => { if (h.closest('main, .card')) convertAfter(h); });
    root.querySelectorAll('p.explain').forEach(convertBefore);
  };
  if (research) {
    const main = document.querySelector('main');
    if (main) {
      sweep(main);
      let pending = false;
      new MutationObserver(() => { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; sweep(main); }); }).observe(main, { childList: true, subtree: true });
    }
  }
  const place = i => {
    const b = i.querySelector('.info-b').getBoundingClientRect(), t = i.querySelector('.info-t');
    const w = Math.min(400, innerWidth - 24);
    t.style.left = Math.max(12, Math.min(b.left - 10, innerWidth - w - 12)) + 'px';
    t.style.top = (b.bottom + 6) + 'px';
    const h = t.getBoundingClientRect().height;
    if (h && b.bottom + 6 + h > innerHeight - 8 && b.top - 6 - h > 8) t.style.top = (b.top - 6 - h) + 'px';
  };
  const close = keep => document.querySelectorAll('.info.pinned').forEach(i => {
    if (i === keep) return;
    i.classList.remove('pinned'); i.querySelector('.info-b').setAttribute('aria-expanded', 'false');
  });
  document.addEventListener('click', e => {
    if (e.target.closest('.info-t')) return;
    const b = e.target.closest('.info-b'), i = b && b.parentElement;
    close(i);
    if (!i) return;
    e.preventDefault(); e.stopPropagation();
    b.setAttribute('aria-expanded', String(i.classList.toggle('pinned')));
    place(i);
  }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(null); });
  for (const ev of ['mouseover', 'focusin']) document.addEventListener(ev, e => { const i = e.target.closest && e.target.closest('.info'); if (i) requestAnimationFrame(() => place(i)); });
  addEventListener('scroll', () => document.querySelectorAll('.info.pinned').forEach(place), { passive: true });
  // the switch between the two versions, outside the public site while they are compared
  if (research && location.hostname !== 'plenar-radar.de' && document.documentElement.dataset.design) {
    const s = document.createElement('div');
    s.className = 'dsw'; s.setAttribute('aria-label', 'Designversion');
    const cur = document.documentElement.dataset.design;
    s.innerHTML = ['a', 'b'].map(v => `<button type="button" data-v="${v}" aria-pressed="${v === cur}">Version ${v.toUpperCase()}</button>`).join('');
    s.addEventListener('click', e => { const v = e.target.dataset.v; if (!v) return; localStorage.setItem('design', v); document.documentElement.dataset.design = v; s.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x.dataset.v === v)); });
    document.body.appendChild(s);
  }
})();
