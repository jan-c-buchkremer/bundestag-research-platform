# Changelog

One entry per release (`docs/release.md`). Each starts with one sentence: what can a reader do now that they could
not before? If that sentence is hard to write, the release is not a finished vertical slice yet.

## Unreleased

## v0.3.0 (2026-11-21)

Readers read every question of a Fragestunde with its answer, see the members of a Fraktion or Gremium with their
photo, find the hib reports on a Vorgang, get from a Sitzungswoche straight to the Radar's summary of it, and move
through every page in one design with the Radar.

- „Wer stimmt wie ich?“ is off until its choice of questions is trusted to show positions without a bias
  (`compass.PUBLISHED`): no page links to it, and `kompass.html` leads to the Abstimmungen.
- Design B is the only design; the switch between A and B is gone.
- CI runs on ubuntu-24.04: Playwright 1.55 cannot install Chromium on the new ubuntu-latest (26.04).
- Themen: the overview as a head card and one row per theme with its Fraktion mix, its last speech and its size
  next to the largest theme. Long page titles (a Rede or Vorgang named after a whole bill) are set smaller.

- The search page in the design of the other pages: a head card with the field, examples and a pill per kind of
  result; people, places, Vorgänge (with their phase pill) and themes as cards with „Alle N zeigen“; Fraktion colours
  in the filters, each filter group folds and the whole column hides („Filter ausblenden“, kept for the next visit).
  Excerpts no longer start with the hidden filter labels or the page head; Anfragen show their date. An empty
  search in the top bar opens the search page.
- A site icon (the hemicycle of the logo, `favicon.svg`, `favicon.ico`, `apple-touch-icon.png`) and tab titles in
  one form: the page's own name, cut at a word after 64 characters, then „| plenar-radar.de“ (`ui.tab_title`).
- One design language with the Radar (`design.css`): a head card with a title line and pills that jump to the
  sections, section headings with their count as a pill, explanations behind an info button, a bluish ground.
- Fraktion, Gremium and the Rollen on the Abgeordnete page: people as cards with photo, role and Fraktion; a
  Fraktion's head in its colour with four numbers; the Gremien index shows each Fraktion's seats.
- Speeches carry their Fraktion as a chip; Text, Themenlandschaft and Protokoll are small pill links.
- Vorgang: the phase of each step as a coloured pill, and „In den Nachrichten: hib“: the reports of „heute im
  bundestag“ whose subject is one of its Drucksachen, as title and link to bundestag.de.
- Sitzungswoche: the Radar's generated summary of the week in a violet box with the way to the week on the Radar,
  the sittings as cards, the week as four tiles that unfold (Beschlüsse, Aktuelle Stunden, Ordnungsmaßnahmen,
  Gesetzgebung with each bill's steps), and the week's hib reports.
- Sitzungen: a chapter per year, a heading per month, the sitting weeks as pills in the calendar strip. Each week
  spans the page: its counts, the way to its page and its Themenlandschaft, and its sittings side by side with
  their counts and the debate with the most speeches.
- Vorgänge: each row shows its stand as a pill in the colours of the phases on a Vorgang's page, as does the
  pipeline of the Gesetzgebung. The list can be ordered by the last step, by the first step (newest or oldest
  first) or by the number of steps; the date column follows the order.
- Front page: the Radar box leads to the Radar's start page and its parts.
- Fragen: each Fragestunde has its page (`regierung/fragestunde/`), every question called with its printed
  wording, the answer and the follow-ups. A Regierungsbefragung or Fragestunde filters its questions by the
  asker's Fraktion, by who answered and by words. The overview shows the newest three Befragungen, each leading to
  its page. Schriftliche and Mündliche Fragen name their asker per question (DIP's activities), so the Fraktion
  filter and the count by Fraktion cover nearly all of them. Ressorts without a hit fold behind one button.
- Debattenkultur: a head card with jump pills, each chart in a card, the explanations behind info buttons, and the
  Ordnungsmaßnahmen as rows with the newest five shown.
- Stylesheets and scripts are linked with a version stamp, so no browser keeps an old copy after a release.

## v0.2.3 (2026-10-16)

Readers can see on the Datenschutz page what the server records about a visit: an access log with shortened IP
addresses and a reader count without cookies.

- Datenschutz: the server keeps an access log with shortened IP addresses for 14 days, and every page reports its
  view to a reader count on the same server (GoatCounter, no cookies, infra `services/stats`).

## v0.2.2 (2026-10-06)

Readers on a phone can open a Steckbrief from the parliament views with a second tap and reach every section through a
menu instead of a bar that scrolled sideways.

- Parliament views: a second tap within finger reach of the seat, or on its tooltip, opens the Steckbrief.
- Phone header: "Menü" folds the sections out as a list; the open search field covers the bar with its icon inside.
- Sachgebiete and Gremien: rows of identical tiles that fill one rectangle, the larger items in fewer, taller tiles.
- Front page: the Radar section in the same plain form as Recherche, violet instead of blue.
- Dates: no page shows a date in another numeric form than dd.mm.yyyy (#64).

## v0.2.1 (2026-10-06)

The build fits its 6g container again: the 10,662 Einzelfrage pages leave the full-text search, which took Pagefind
from 4.4 to 5.5 GB. They stay findable by title in the Einzelfragen list; the Anfragen and Befragungen stay in the
search.

## v0.2.0 (2026-10-06)

Readers can read every question to the government and its answer on the site: each Kleine and Große Anfrage with its
questions, answers and tables, each Mündliche and Schriftliche Frage, and each Regierungsbefragung with every
question, answer and follow-up.

- `regierung/anfragen.html`, `regierung/einzelfragen.html`, `regierung/regierungsbefragung.html`
  (`question_pages.py`, new), from the foundation's question tables (v0.2.0): lists newest first with charts as
  filters, and a page per Anfrage, per Frage and per Befragung. An answer the foundation could not read says
  "Antwort nicht lesbar" and links the PDF. The question pages are in the search; the answers are not. The Vorgang
  pages of the Mündliche Fragen forward to their question page (#62).
- `vorgaenge/index.html`: the Vorgänge in six groups by what the instrument does (Gesetzgebung, Anträge und
  Beschlüsse, Wahlen und Besetzungen, Einzelfälle aus Ausschüssen, Unterrichtungen und Haushaltskontrolle, Fragen),
  DIP's Art below; the 1,623 Mündliche Fragen leave the list and a note names every kind of Frage with its count. A
  DIP "Petition" is called a Sammelübersicht. The activity strip leaves out a quarter label without room (#61).
- From the foundation instead of the site's own rules: a decision's Vorgänge (`decision_vorgang`, a decision on
  several Vorgänge in full only on its own page, #43), who a speech counts for and a member's fraction (a speech in a
  government office counts for the Bundesregierung everywhere, #44), the parts of a speech and one address per speech
  (#45); the Ausschuss filter of the Abgeordnete list follows the Gremium pages (#46); a retired placeholder person id
  forwards to the card (#47). These need a store from foundation v0.1.0 or later.

- UI check (`scripts/ui_check.py`, `scripts/ui_check.sh`, `tests/test_ui.py`, in CI): every kind of page at desktop
  and phone width, errors and screenshot comparison. Its first run found and this release fixes:
  - the Orte page's script did not run: a line was split inside its JavaScript, so no place search and no map;
  - the week strip's bars and the calendar's week cards shared the class `.wk`: on Sitzungen the sittings of a week
    stood side by side and the page was 1,819 px wide (the strip's bars are now `.swk`);
  - Radar links did not wrap: on a phone the front page was 802 px wide.

Readers pick by seeing: on the Vorgänge, Sachgebiete, EU-Vorlagen, Abstimmungen, Fragen, Geschlossenheit,
Debattenkultur and Gremien pages every chart is also a filter, the filters combine, and the selection is in the
address, so it can be shared and the back button undoes it.

- `controls.py` and `controls.js` (new): tile field, fraction chips, pipeline, segmented bar, stacked bar rows and an
  activity strip, drawn in Python at build time, each part a button, each chart with "Als Tabelle". Without
  JavaScript the page shows the chart, its table and the full list.
- `vorgaenge/index.html`: the kinds as a segmented bar, the Gesetzgebungsvorgänge as a pipeline from "Eingebracht" to
  "Verkündet" with the branch "beendet ohne Gesetz" (the DIP Stände mapped in `procedures.STAGE`), the Einbringer as
  chips, a strip of the weeks. The selects "jede Art" and "jeder Stand" are gone. Long lists show the newest 30 and
  "mehr anzeigen".
- `sachgebiete/index.html`: a tile per Sachgebiet, its width by its Vorgänge, the table behind "Als Tabelle".
  `sachgebiete/<slug>.html`: the Einbringer as stacked bar rows that filter the Vorgänge, and the controls of the
  Vorgänge index.
- `vorgaenge/eu-vorlagen.html`: the Stand as a row of steps, the lead committees as chips (once the store has the
  referral table), the strip. `abstimmungen/index.html`: chips for namentlich, per Handzeichen, angenommen and
  abgelehnt instead of the two selects, and the strip; old `#art=…&ergebnis=…` links keep working.
- `regierung/index.html` (Fragen): the statistics are charts, and a click on one opens its list filtered (the
  Kleine Anfragen of a fraction or a month, the turns of one Regierungsbefragung). Each kind's list has chips for
  Fraktion, Ressort and Stand, the answer time as a bar and a column per month instead of the five selects.
- `abstimmungen/geschlossenheit.html`: a fraction's row of the small multiples shows its dissents; chips for
  Fraktion and own vote and the strip instead of the select.
- `debatte/index.html`: small multiples per fraction instead of the three tables of "Ton und Ordnung" (the tables
  behind "Als Tabelle"); the Ordnungsmaßnahmen are a list filtered by a card, kind, fraction and week.
- `gremien/index.html`: a tile per Gremium, its width by its current members, the bar its fractions, filtered by
  kind and name, "Als Liste" for a plain list. A Gremium's page filters its members by fraction, role and name.
- A Vorgang's date in lists is its latest step until the build date, so a law with an Inkrafttreten in 2030 no
  longer sorts first; the row says "tritt am … in Kraft".
- CI installs Node, and the tests that run the page scripts in Node fail there instead of being skipped.

Readers can open any of DIP's Sachgebiete and see what the 21st Bundestag did in it: the Vorgänge by kind and
Einbringer, the speeches, the decisions and the Drucksachen; the EU-Vorlagen have a page of their own.

- `sachgebiete/index.html` (`subjects.py`): every Sachgebiet with its Vorgänge (Gesetzgebung, Anträge, Kleine
  Anfragen), how many were debated, and the decisions, largest first. Below it what has no Sachgebiet: Fragen,
  EU-Vorlagen, Petitionen, and the plenary business without a Vorgang.
- `sachgebiete/<slug>.html`: an entity page per Sachgebiet with the facets Einbringer, Vorgänge (filterable, a
  Vorgang without a page here links DIP), Reden, Abstimmungen und Beschlüsse, Drucksachen.
- `vorgaenge/eu-vorlagen.html` (`eu.py`): every EU-Vorlage with its Unterrichtung and a Stand from DIP's steps,
  filterable, linked with the Sachgebiet "Europapolitik und Europäische Union". The Ausschuss column waits for the
  foundation's referral table.
- Vorgänge has the sub-tabs Vorgänge | Sachgebiete | EU-Vorlagen. The Sachgebiete on a Vorgang page link their pages;
  the search finds Sachgebiete; the front page has a Sachgebiete tile; the Thema pages link the Sachgebiete.

Readers arriving at plenar-radar.de land on a front page that shows what the site offers and takes them there in
one click, and every page shows by its colour whether it states checkable facts (Recherche, blue) or selects and
interprets (Radar, violet).

- Front page `index.html` (`landing.py`): the house as it sits today, every seat linked to its card; the record in
  numbers; Recherche and Radar side by side; the latest sitting week and roll-call votes. The Abgeordnete list moved
  to `abgeordnete.html`, and old `/#…` links are forwarded there.
- `shell.css` (new, linked before `cards.css`): tokens, the header with its mode and the Radar elements. The top bar
  has the site's name in the centre and a violet Radar entry at the end.
- Kompass and Themen are Radar pages, with a method note above the footer. Every link into the Themenlandschaft
  and every topic chip is a Radar element.
- The Themen index no longer squeezes titles into the date column.

## v0.1.0 (2026-10-04)

Readers can look up every member of the 21st Bundestag at plenar-radar.de – speeches, votes, Drucksachen, committees,
their Wahlkreis – and follow every Vorgang, sitting and decision, each fact linked to its source.

The first tag: the site as it is live on 2026-10-04, with the compass on the foundation's stable decision ids.
