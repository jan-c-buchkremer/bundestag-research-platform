"""Die Woche im Bundestag: `woche/<iso week>.html`, the sitting week in the time hierarchy (docs/plan.md 11.5, D18):
Wahlperiode (`sitzungen/index.html`) → week → sitting → agenda item, with breadcrumbs up and links down. Also the
Atom feed `woche/feed.xml`; `woche/index.html` is a stub to the Wahlperiode page.

A week page is an entity page: a header with the link to the landscape's week page for the topic map (which it
does not duplicate), the week in a few sentences, and the facets Sitzungen, Reden, Abstimmungen und Beschlüsse and
Drucksachen (the Vorlagen on the week's agenda), drawn by facts.py. Every sentence is a fixed template filled with
counts and titles from the store; no text is generated. It says on how many days the Bundestag sat, how many
decisions were taken and which roll-call votes, which Aktuelle Stunden were held on whose request, the chair's
Ordnungsmaßnahmen (debate.py's rule-based reading) and, when the store has `vorgang_position`, the bills with a
step that week. Its Vorgänge and its Abstimmungen are facets of their own.

The Wahlperiode page `sitzungen/index.html` is a calendar of the sitting weeks (docs/plan.md 12.4, D29), in the
visual language of the landscape's week overview (D10): a strip per year with the sitting weeks, then one card per
week with its sittings; toggles reveal per week, or for all weeks, each sitting's Abstimmungen (facts.decision,
with result and roll call or show of hands) and the Vorgänge that moved forward that day (debated, decided, or a
DIP step in the Bundestag), each linked to its page. Every vote shown here is the same component as on the sitting
page and on the Vorgang timeline; there is no third renderer."""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from research import data, debate, facts, redirects, urls
from research.data import has_table, page_id
from research.ui import (
    FOOTER,
    LANDSCAPE,
    MONTHS,
    RADAR_ICON,
    RESEARCH,
    SITTING_TABS,
    WEEKDAYS,
    crumbs,
    e,
    entity_header,
    facet,
    long_date,
    n,
    shell,
    short_date,
    stat_tiles,
    subtabs,
)

# where this site is published: the feed needs absolute links
BASE = RESEARCH
ATOM = "http://www.w3.org/2005/Atom"
FEED_WEEKS = 20
BILLS = 6  # Gesetzesvorhaben shown in a week's summary before "alle zeigen"
NUMBERS = {1: "einem", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf"}


def plural(k: int, one: str, many: str) -> str:
    """ "1 Rede", "3 Reden"; "eine" is left to the sentence."""
    return f"{n(k)} {one if k == 1 else many}"


def week_label(week: str) -> str:
    y, w = week.split("-W")
    return f"Sitzungswoche {int(w)}/{y}"


def week_span(week: str) -> tuple[str, str]:
    y, w = week.split("-W")
    monday = dt.date.fromisocalendar(int(y), int(w), 1)
    return monday.isoformat(), (monday + dt.timedelta(days=6)).isoformat()


def group(sittings: list[dict]) -> dict[str, list[dict]]:
    """Sittings by ISO week, newest week first, sittings in order within a week."""
    weeks: dict[str, list[dict]] = defaultdict(list)
    for s in sorted(sittings, key=lambda s: (s["date"], s["number"])):
        weeks[s["week"]].append(s)
    return dict(sorted(weeks.items(), reverse=True))


def current_hours(ss: list[dict]) -> list[dict]:
    """Aktuelle Stunden: agenda items whose title starts "Aktuelle Stunde | auf Verlangen der Fraktion … | topic"."""
    out = []
    for s in ss:
        for i in s["items"]:
            seg = i["segments"]
            if seg and seg[0].startswith("Aktuelle Stunde"):
                by = next((x for x in seg[1:] if x.startswith("auf Verlangen")), None)
                topic = next((x for x in seg[1:] if x != by and not x.startswith("(")), None)
                out.append({"sitting": s, "position": i["position"], "by": by, "topic": topic or i["title"]})
    return out


def bill_steps(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """{week: [{vorgang, title, date, position, chamber}]} from `vorgang_position`; empty without the table."""
    if not has_table(conn, "vorgang_position") or not has_table(conn, "vorgang"):
        return {}
    out: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(
        """SELECT p.vorgang_id, v.title, p.date, p.position, p.chamber FROM vorgang_position p
           JOIN vorgang v ON v.id = p.vorgang_id WHERE v.type = 'Gesetzgebung' ORDER BY p.date, v.title"""
    ):
        y, w, _ = dt.date.fromisoformat(r[2][:10]).isocalendar()
        out[f"{y}-W{w:02d}"].append({"vorgang": r[0], "title": r[1], "date": r[2][:10], "position": r[3],
                                     "chamber": r[4]})  # fmt: skip
    return out


def vorgang_steps(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """{date: [{vorgang, title, position}]}: every Vorgang's DIP steps in the Bundestag (`vorgang_position`, chamber
    BT), by date; empty without the table."""
    if not has_table(conn, "vorgang_position") or not has_table(conn, "vorgang"):
        return {}
    out: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(
        """SELECT p.vorgang_id, v.title, p.date, p.position FROM vorgang_position p
           JOIN vorgang v ON v.id = p.vorgang_id WHERE p.chamber = 'BT' ORDER BY p.date, p.id"""
    ):
        out[r[2][:10]].append({"vorgang": r[0], "title": r[1], "position": r[3]})
    return out


def moves(ss: list[dict], decided: list[dict], steps: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """The Vorgänge that moved forward in each sitting, {sitting id: [{id, title, what: [..]}]}: debated under one of
    its agenda items or sub-items, decided there (data.decisions' Vorgänge of each decision), or a DIP step in the
    Bundestag on that day. Every Vorgang once per sitting, in agenda order."""
    by_sitting: dict[str, list[dict]] = defaultdict(list)
    for d in sorted(decided, key=lambda d: d["order"]):
        if d["sitting"]:
            by_sitting[d["sitting"]].append(d)
    out = {}
    for s in ss:
        found: dict[str, dict] = {}
        add = _adder(found)
        for i in s["items"]:
            for v in i.get("vorgaenge") or []:
                add(v["id"], v["title"], f"beraten ({i['label']})")
            for sub in i.get("sub_items") or []:
                for v in sub.get("vorgaenge") or []:
                    add(v["id"], v["title"], f"beraten ({i['label']} › {sub['label']})")
        for d in by_sitting.get(s["id"], []):
            for vid in d.get("vorgaenge") or []:
                add(vid, d["vorgang_titles"].get(vid, vid), "abgestimmt")
        for st in steps.get(s["date"], []):
            add(st["vorgang"], st["title"], st["position"])
        out[s["id"]] = list(found.values())
    return out


def _adder(found: dict[str, dict]):
    def add(vid: str, title: str, what: str) -> None:
        x = found.setdefault(vid, {"id": vid, "title": title, "what": []})
        if what not in x["what"]:
            x["what"].append(what)

    return add


def gather(ss: list[dict], decided: list[dict], measures: list[dict], steps: list[dict],
           moved: dict[str, list[dict]] | None = None) -> dict:  # fmt: skip
    """Everything a week page says, as data (the templates below turn it into sentences)."""
    ids = {s["id"] for s in ss}
    return {
        "moves": {s["id"]: (moved or {}).get(s["id"], []) for s in ss},
        "sittings": ss,
        "days": sorted({s["date"] for s in ss}),
        "speeches": sum(len(i["speeches"]) for s in ss for i in s["items"]),
        "items": sum(len(s["items"]) for s in ss),
        "decisions": [d for d in decided if d["sitting"] in ids],
        "hours": current_hours(ss),
        "measures": [m for m in measures if m["sitting"] in ids],
        "steps": steps,
    }


def _a(href: str, text: str) -> str:
    return f'<a href="{e(href)}">{e(text)}</a>'


def sentences(w: dict, root: str, have: set[str] | None = None, votes: bool = True,
              fold: bool = True) -> list[tuple[str, str]]:  # fmt: skip
    """(heading, HTML) per section; `root` is "../" on the page and BASE in the feed, `have` the Vorgang pages that
    exist (None: link every one). `votes`: list the roll-call votes (the feed; the page has them as a facet);
    `fold`: the Gesetzgebung list after BILLS behind a toggle."""
    out = []
    days = w["days"]
    k = len(days)
    day_word = "an einem Tag" if k == 1 else f"an {NUMBERS.get(k, n(k))} Tagen"
    sits = ", ".join(
        f"{_a(f'{root}sitzungen/{s["page"]}.html', f'{s["number"]}. Sitzung')} am "
        f"{WEEKDAYS[dt.date.fromisoformat(s['date']).weekday()]}, {e(long_date(s['date']))}"
        for s in w["sittings"]
    )
    out.append(("Sitzungen", f"<p>Der Bundestag hat in dieser Woche {day_word} getagt: {sits}. Es gab "
                             f"{plural(w['speeches'], 'Rede', 'Reden')} zu "
                             f"{plural(w['items'], 'Tagesordnungspunkt', 'Tagesordnungspunkten')}.</p>"))  # fmt: skip
    ds = w["decisions"]
    if ds:
        res = Counter(d["result"] for d in ds)
        rest = len(ds) - res["angenommen"] - res["abgelehnt"]
        text = (f"<p>Der Bundestag hat {plural(len(ds), 'Beschluss', 'Beschlüsse')} gefasst: "
                f"{n(res['angenommen'])} angenommen, {n(res['abgelehnt'])} abgelehnt"
                + (f", {n(rest)} mit anderem oder ohne Ergebnis" if rest else "") + ".</p>")  # fmt: skip
        rc = sorted((d for d in ds if d["kind"] == "namentlich"), key=lambda d: (d["date"], d["order"]))
        if rc:
            lead = "Eine Abstimmung war" if len(rc) == 1 else f"{n(len(rc))} Abstimmungen waren"
            rows = "".join(facts.decision(d, root, agenda=False) for d in rc) if votes else ""
            text += f"<p>{lead} namentlich.</p>{rows}"
        out.append(("Beschlüsse", text))
    else:
        out.append(("Beschlüsse", "<p>Für diese Woche sind keine Beschlüsse im Datenbestand.</p>"))
    if w["hours"]:
        rows = "".join(
            f'<li>{_a(f"{root}sitzungen/{h["sitting"]["page"]}.html#top-{h["position"]}", h["topic"])}'
            + (f" ({e(h['by'])})" if h["by"] else "") + "</li>"
            for h in w["hours"]
        )  # fmt: skip
        k = len(w["hours"])
        lead = "Es gab eine Aktuelle Stunde" if k == 1 else f"Es gab {n(k)} Aktuelle Stunden"
        out.append(("Aktuelle Stunden", f"<p>{lead}:</p><ul>{rows}</ul>"))
    ms = w["measures"]
    if ms:
        kinds = Counter(m["kind"] for m in ms)
        what = ", ".join(plural(v, kind, {"Ordnungsruf": "Ordnungsrufe", "Rüge": "Rügen"}.get(kind, kind + "e"))
                         for kind, v in kinds.items())  # fmt: skip
        rows = "".join(
            f'<li>{e(m["kind"])} am {_a(f"{root}sitzungen/{page_id(m["sitting"])}.html", long_date(m["date"]))}, '
            + ("Fraktion nicht eindeutig" if m["fraction"] == debate.UNCLEAR else f"an {e(m['fraction'])}") + "</li>"
            for m in ms
        )  # fmt: skip
        out.append(("Ordnungsmaßnahmen", f"<p>Die Sitzungsleitung hat {what} erteilt, so wie das Protokoll es "
                                         f"festhält:</p><ul>{rows}</ul>"))  # fmt: skip
    else:
        out.append(("Ordnungsmaßnahmen", "<p>Im Protokoll dieser Woche ist kein Ordnungsruf, keine Rüge und kein "
                                         "Sitzungsausschluss erkannt worden.</p>"))  # fmt: skip
    if w["steps"]:
        by: dict[str, list[dict]] = {}
        for b in w["steps"]:
            by.setdefault(b["vorgang"], []).append(b)

        def bill(bs: list[dict]) -> str:  # one Vorgang: its title, then each step of the week as a small pill
            b = bs[0]
            title = (_a(f"{root}{urls.vorgang(b['vorgang'])}", b["title"]) if have is None or b["vorgang"] in have
                     else e(b["title"]))  # fmt: skip
            pills = "".join(
                f'<span class="stp{" br" if x["chamber"] == "BR" else ""}">{e(x["position"])}'
                f"<small>{e(short(x['date']))}{' · Bundesrat' if x['chamber'] == 'BR' else ''}</small></span>"
                for x in bs
            )
            return f'<li><span class="bt">{title}</span><span class="stps">{pills}</span></li>'

        items = [bill(bs) for bs in by.values()]
        k = len(items)
        lead = "Ein Gesetzesvorhaben hatte" if k == 1 else f"{n(k)} Gesetzesvorhaben hatten"
        shown, rest = (items[:BILLS], items[BILLS:]) if fold else (items, [])
        more = (f'<details class="wk-more"><summary>Alle {n(k)} Vorhaben zeigen</summary>'
                f'<ul class="wk-bills">{"".join(rest)}</ul></details>' if rest else "")  # fmt: skip
        out.append(("Gesetzgebung", f"<p>{lead} in dieser Woche einen Schritt im Verfahren:</p>"
                                    f'<ul class="wk-bills">{"".join(shown)}</ul>{more}'))  # fmt: skip
    return out


def radar_box(week: str, lead: dict | None, latest: bool) -> str:
    """The week on the Radar, marked as interpretation (docs/architecture.md). With the Radar's generated summary of
    this week (`lead`, data.radar_lead), its text in a violet box and the way to the whole week on the Radar's start
    page; for any other week the way to the week's Themenlandschaft."""
    mark = f'<span class="rmark">{RADAR_ICON}Radar</span>'
    land = f'<a class="wr-btn" href="{LANDSCAPE}{e(week)}.html">Themenlandschaft dieser Woche →</a>'
    if lead and lead["week"] == week:
        paras: dict[int, list[str]] = defaultdict(list)
        for x in lead["sentences"]:
            paras[x.get("paragraph") or 0].append(e(x["text"]))
        ps = [f"<p>{' '.join(xs)}</p>" for _, xs in sorted(paras.items())]
        text = "".join(ps[:2]) + (f'<details class="wr-rest"><summary>Weiterlesen</summary>{"".join(ps[2:])}'
                                  "</details>" if len(ps) > 2 else "")  # fmt: skip
        whole = (f'<a class="wr-btn" href="{LANDSCAPE}index.html#sitzungswoche">Die ganze Woche im Radar →</a>'
                 if latest else "")  # fmt: skip
        return (f'<section class="wk-radar"><div class="wr-head">{mark}<h2>Die Woche im Bundestag</h2>'
                f'<span class="wr-auto">automatisch erstellt</span></div><div class="wr-lead">{text}</div>'
                f'<p class="wr-note">{e(lead["label"])} Die Quellen jedes Satzes stehen im Radar.</p>'
                f'<div class="wr-go">{whole}{land}</div>'
                '<p class="wr-more">Im Radar außerdem: steigende Themen, „Beraten und entschieden“ mit den '
                "Positionen der Fraktionen und die Meldungen der Woche.</p></section>")  # fmt: skip
    return (f'<section class="wk-radar compact"><div class="wr-head">{mark}<h2>Diese Woche im Radar</h2></div>'
            "<p>Die Reden dieser Woche als Landkarte ihrer Themen, automatisch nach Ähnlichkeit geordnet.</p>"
            f'<div class="wr-go">{land}<a class="wr-link" href="{LANDSCAPE}index.html">Zum Radar</a></div>'
            "</section>")  # fmt: skip


def week_hib(w: dict, hib: dict[str, list[dict]], have: set[str]) -> list[tuple[dict, str, str]]:
    """The hib items of this week's dates on the Vorgänge that moved this week: (item, Vorgang id, title)."""
    frm, to = w["days"][0], w["days"][-1]
    frm = (dt.date.fromisoformat(frm) - dt.timedelta(days=dt.date.fromisoformat(frm).weekday())).isoformat()
    to = (dt.date.fromisoformat(frm) + dt.timedelta(days=6)).isoformat()
    seen: dict[str, tuple[dict, str, str]] = {}
    for xs in w["moves"].values():
        for x in xs:
            if x["id"] not in have:
                continue
            for h in hib.get(str(x["id"]), []):
                if frm <= h["date"][:10] <= to:
                    seen.setdefault(h["id"], (h, x["id"], x["title"]))
    return sorted(seen.values(), key=lambda t: (t[0]["date"], t[0]["id"]), reverse=True)


def sitting_cards(w: dict) -> str:
    """The week's sittings as cards: weekday and date, number, and three counts."""
    by = Counter(d["sitting"] for d in w["decisions"])
    cards = []
    for s in w["sittings"]:
        day = WEEKDAYS[dt.date.fromisoformat(s["date"]).weekday()]
        k_sp = sum(len(i["speeches"]) for i in s["items"])
        counts = "".join(f"<span><b>{n(v)}</b>{label}</span>" for v, label in (
            (len(s["items"]), "TOPs"), (k_sp, "Reden"), (by[s["id"]], "Beschlüsse")))  # fmt: skip
        cards.append(f'<a class="sitc" href="../{e(urls.sitting(s["id"]))}"><span class="sd">{e(day)}, '
                     f'{e(long_date(s["date"]))}</span><b class="sno">{s["number"]}. Sitzung</b>'
                     f'<span class="sk">{counts}</span></a>')  # fmt: skip
    return f'<div class="sitcs">{"".join(cards)}</div>'


def overview(w: dict, root: str, have: set[str]) -> str:
    """„Die Woche im Überblick“ as four tiles in a fixed order (Beschlüsse, Aktuelle Stunden, Ordnungsmaßnahmen,
    Gesetzgebung): a number, one sentence, and the full list to unfold. The sentences come from `sentences`, the same
    templates as the feed."""
    said = dict(sentences(w, root, have, votes=False, fold=False))  # the tile itself unfolds
    ds = w["decisions"]
    rc = sorted((d for d in ds if d["kind"] == "namentlich"), key=lambda d: (d["date"], d["order"]))
    votes = "".join(
        f'<li><span class="badge {e(d["result"] or "")}">{e(d["result"] or "ohne Ergebnis")}</span> '
        f'<a href="{root}{e(urls.decision(d))}">{e(d["title"])}</a></li>'
        for d in rc
    )
    bills = len({b["vorgang"] for b in w["steps"]})

    def tile(key: str, title: str, k: int, line: str, more: str = "", label: str = "Alle zeigen") -> str:
        unfold = f'<details><summary>{label}</summary><div class="ov-more">{more}</div></details>' if more else ""
        return (f'<div class="ov ov-{key}"><h3>{title}</h3><b class="ov-n">{n(k)}</b>'
                f'<p class="ov-l">{line}</p>{unfold}</div>')  # fmt: skip

    res = Counter(d["result"] for d in ds)
    tiles = [
        tile("dec", "Beschlüsse", len(ds),
             f"{n(res['angenommen'])} angenommen, {n(res['abgelehnt'])} abgelehnt, {n(len(rc))} namentlich."
             if ds else "Keine Beschlüsse im Datenbestand.",
             f"<ul>{votes}</ul>" if votes else "", "Die namentlichen Abstimmungen"),
        tile("hours", "Aktuelle Stunden", len(w["hours"]),
             "Auf Verlangen einer Fraktion oder vereinbart." if w["hours"] else "Keine in dieser Woche.",
             said.get("Aktuelle Stunden", "")),
        tile("meas", "Ordnungsmaßnahmen", len(w["measures"]),
             "Ordnungsrufe, Rügen und Ausschlüsse, wie das Protokoll sie festhält." if w["measures"]
             else "Keine im Protokoll erkannt.",
             said.get("Ordnungsmaßnahmen", "") if w["measures"] else ""),
        tile("bills", "Gesetzgebung", bills,
             "Gesetzesvorhaben mit einem Schritt im Verfahren." if bills else "Kein Schritt in dieser Woche.",
             said.get("Gesetzgebung", ""), "Die Vorhaben und ihre Schritte"),
    ]  # fmt: skip
    return f'<div class="ovs">{"".join(tiles)}</div>'


def week_page(week: str, w: dict, prev: str | None, nxt: str | None, have: set[str],
              lead: dict | None = None, hib: dict[str, list[dict]] | None = None) -> str:  # fmt: skip
    frm, to = week_span(week)
    nav = (f'<a href="{e(prev)}.html">← {e(week_label(prev))}</a>' if prev else "<span></span>") + (
        f'<a class="next" href="{e(nxt)}.html">{e(week_label(nxt))} →</a>' if nxt else "")  # fmt: skip
    sps = [sp for s in w["sittings"] for i in s["items"] for sp in i["speeches"]]
    ds = sorted(w["decisions"], key=lambda d: (d["date"], d["order"]))
    res = Counter(d["result"] for d in ds)
    refs = list({r["number"]: r for s in w["sittings"] for i in s["items"] for r in i["drucksachen"]}.values())
    n_moved = len({x["id"] for xs in w["moves"].values() for x in xs if x["id"] in have})
    news = week_hib(w, hib or {}, have)
    of = {h["id"]: (f"../{urls.vorgang(v)}", t) for h, v, t in news}  # each item's Vorgang: (href, title)
    pills = [(f"<b>{len(w['sittings'])}</b> {'Sitzung' if len(w['sittings']) == 1 else 'Sitzungen'}", "#sitzungen"),
             (f"<b>{n(len(sps))}</b> Reden", "#reden"), (f"<b>{n(len(ds))}</b> Beschlüsse", "#abstimmungen"),
             (f"<b>{n(n_moved)}</b> Vorgänge", "#vorgaenge")]  # fmt: skip
    if news:
        pills.append((f"<b>{n(len(news))}</b> hib-Meldungen", "#hib"))
    stats = stat_tiles(
        [
            (n(len(sps)), "Reden"),
            (n(res["angenommen"]), "Beschlüsse angenommen"),
            (n(res["abgelehnt"]), "Beschlüsse abgelehnt"),
            (n(sum(1 for d in ds if d["kind"] == "namentlich")), "namentliche Abstimmungen"),
        ]
    )
    body = (
        crumbs(("../sitzungen/index.html", "21. Wahlperiode"), (None, week_label(week)))
        + entity_header(week_label(week), [f"{e(long_date(frm))} bis {e(long_date(to))}"], [
            '<a href="feed.xml">Als Feed abonnieren (Atom)</a>'], when="Sitzungswoche", pills=pills)
        + f'<nav class="prevnext">{nav}</nav>'
        + radar_box(week, lead, nxt is None)
        + facet("sitzungen", "Sitzungen", sitting_cards(w), len(w["sittings"]))
        + facet("woche", "Die Woche im Überblick", stats + overview(w, "../", have),
                explain="Jeder Satz ist aus den Daten gezählt und verlinkt die Sitzung, Abstimmung oder den Vorgang, "
                "aus dem er stammt.")
        + (facet("hib", "In den Nachrichten: hib", facts.hib_list([h for h, _, _ in news], "hib", 6,
                 vorgang=lambda h: of[h["id"]]), len(news),
                 "Meldungen aus hib – heute im bundestag aus dieser Woche zu den Vorgängen, die in dieser Woche "
                 "weitergekommen sind. Titel und Link, der Text steht bei der Quelle. © Deutscher Bundestag")
           if news else "")
        + facet("reden", "Reden", facts.speech_list(sps, "../", "reden", where=True), len(sps))
        + facet("vorgaenge", "Vorgänge", moved_rows(w, "../", have), n_moved,
                "Vorgänge mit einem Fortschritt in dieser Woche: im Plenum beraten, abgestimmt oder mit einem "
                "Schritt im Bundestag laut DIP. Ein Vorgang erstreckt sich meist über mehrere Wochen. Sein ganzer "
                "Ablauf steht auf seiner Seite.")
        + facet("abstimmungen", "Abstimmungen und Beschlüsse", facts.decision_list(ds, "../", "dec"), len(ds))
        + facet("drucksachen", "Drucksachen", f"<p>{facts.drucksache_list(refs, '../', limit=40)}</p>" if refs
                else '<p class="explain">Keine Drucksachen auf der Tagesordnung.</p>', len(refs),
                "Die Vorlagen auf der Tagesordnung dieser Woche.")
        + f"<footer>{FOOTER}</footer>"
    )  # fmt: skip
    return shell(root="../", kind="p-week", active="sittings", title=week_label(week),
                 desc=f"Der 21. Bundestag in der {week_label(week)}: Sitzungen, Reden, Beschlüsse.", body=body,
                 data={"kind": "week", "id": week},
                 head='<link rel="alternate" type="application/atom+xml" title="Die Woche im Bundestag" '
                      'href="feed.xml">')  # fmt: skip


def moved_rows(w: dict, root: str, have: set[str]) -> str:
    """The week's Vorgänge, by sitting: what happened to each, linked to its page."""
    rows = []
    for s in w["sittings"]:
        for x in w["moves"].get(s["id"], []):
            if x["id"] not in have:
                continue
            rows.append(f'<div class="row"><div class="d">{e(short(s["date"]))}</div><div class="t">'
                        f'<a href="{root}{e(urls.vorgang(x["id"]))}">{e(x["title"])}</a>'
                        f'<div class="sub">{e(", ".join(x["what"]))} · <a href="{root}{e(urls.sitting(s["id"]))}">'
                        f"{s['number']}. Sitzung</a></div></div></div>")  # fmt: skip
    return facts.fact_list(rows, "vg", "Kein Vorgang ist in dieser Woche weitergekommen.", limit=30)


def short(d: str) -> str:
    return f"{d[8:10]}.{d[5:7]}.{d[:4]}"


def feed(weeks: dict[str, dict], have: set[str] | None = None, limit: int = FEED_WEEKS) -> str:
    """Atom feed of the newest weeks, one entry per week, with absolute links."""
    ET.register_namespace("", ATOM)
    root = ET.Element(f"{{{ATOM}}}feed")

    def sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
        el = ET.SubElement(parent, f"{{{ATOM}}}{tag}", attrs)
        el.text = text
        return el

    def stamp(date: str) -> str:
        return f"{date}T00:00:00Z"

    newest = next(iter(weeks.values()), None)
    sub(root, "title", "Die Woche im Bundestag")
    sub(root, "subtitle", "Jede Sitzungswoche des 21. Deutschen Bundestages in wenigen Sätzen, aus den Daten gezählt.")
    sub(root, "id", f"{BASE}woche/")
    sub(root, "link", href=f"{BASE}woche/feed.xml", rel="self")
    sub(root, "link", href=f"{BASE}{urls.PERIOD}")
    sub(root, "updated", stamp(newest["days"][-1]) if newest else "1970-01-01T00:00:00Z")
    sub(sub(root, "author"), "name", "bundestag-research-platform")
    for week, w in list(weeks.items())[:limit]:
        entry = sub(root, "entry")
        sub(entry, "title", week_label(week))
        sub(entry, "id", f"{BASE}woche/{week}.html")
        sub(entry, "link", href=f"{BASE}woche/{week}.html")
        sub(entry, "updated", stamp(w["days"][-1]))
        html = "".join(f"<h2>{e(h)}</h2>{t}" for h, t in sentences(w, BASE, have))
        sub(entry, "content", html, type="html")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def write(conn: sqlite3.Connection, out: Path, sittings: list[dict], decided: list[dict],
          lead: dict | None = None) -> dict[str, int]:  # fmt: skip
    """Write woche/ and the stub of its old index; call after the sitting, vote and Vorgang pages. Returns
    {"woche": pages}."""
    if not sittings:
        return {}
    measures = debate.order_measures(conn)
    steps = bill_steps(conn)
    bills_dir = out / "vorgaenge"
    have = {p.stem for p in bills_dir.glob("*.html") if p.stem != "index"} if bills_dir.is_dir() else set()
    moved = moves(sittings, decided, vorgang_steps(conn))
    hib = data.hib_by_vorgang(conn)
    weeks = {wk: gather(ss, decided, measures, steps.get(wk, []), moved) for wk, ss in group(sittings).items()}
    (out / "sitzungen").mkdir(parents=True, exist_ok=True)
    (out / urls.PERIOD).write_text(period_page(sittings, decided, moved, have), encoding="utf-8")
    d = out / "woche"
    d.mkdir(parents=True, exist_ok=True)
    keys = list(weeks)  # newest first
    for i, (wk, w) in enumerate(weeks.items()):
        prev = keys[i + 1] if i + 1 < len(keys) else None
        nxt = keys[i - 1] if i else None
        (d / f"{wk}.html").write_text(week_page(wk, w, prev, nxt, have, lead, hib), encoding="utf-8")
    redirects.write(out, "woche/index.html", urls.PERIOD, "21. Wahlperiode: Sitzungswochen und Sitzungen")
    (d / "feed.xml").write_text(feed(weeks, have), encoding="utf-8")
    return {"woche": len(weeks)}


# ---------------------------------------------------------------- the Wahlperiode: a calendar of sitting weeks

PERIOD_STYLE = """<style>
body.p-sittings main { max-width: 1100px; }
.cal .year { font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--faint);
  margin: 26px 0 10px; }
.cal .strip { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 4px; margin: 0 0 6px; }
.cal .strip .m { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 4px 4px 6px;
  min-width: 0; }
.cal .strip .m b { display: block; font-size: 11px; font-weight: 600; color: var(--muted); margin-bottom: 3px; }
.cal .strip .m span, .cal .strip .m a { display: inline-block; font-size: 11px; min-width: 20px; text-align: center;
  border-radius: 5px; padding: 1px 2px; margin: 1px 0; color: var(--faint); font-variant-numeric: tabular-nums; }
.cal .strip .m a { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.cal .tools { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 10px 0 4px; font-size: 13px; }
.cal .tools label { cursor: pointer; }
.cal .grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
.cal .wk { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px;
  min-width: 0; scroll-margin-top: 12px; }
.cal .wk:target { border-color: var(--accent); }
.cal .wk-h { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between;
  gap: 10px 20px; margin: 0 0 12px; }
.cal .wk h3 { margin: 0; font-size: 19px; font-weight: 750; letter-spacing: -.01em; }
.cal .wk .dates { color: var(--muted); font-size: 13px; margin: 2px 0 8px; }
.cal .wk .utags { margin: 0; }
.cal .wk-go { display: flex; flex-wrap: wrap; gap: 8px; }
.cal .wk-btn { display: inline-block; padding: 7px 14px; border-radius: 999px; font-size: 13.5px; font-weight: 650;
  background: var(--research, var(--accent)); color: #fff; }
.cal .wk-btn:hover { text-decoration: none; filter: brightness(1.08); }
.cal .wk-btn.rl { background: var(--radar-soft, #f1ebff); color: var(--radar-ink, #5b21b6); }
.cal .wk .sitcs { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.cal .wk .sitc { min-width: 0; }
.cal .wk .sitc .sno { color: var(--text); }
.cal .wk .sitc .lg { display: block; margin-top: 10px; font-size: 13px; line-height: 1.4; }
.cal .wk .sitc .lg .k { display: block; margin: 0 0 2px; }
.cal .wk .opts { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 13px; color: var(--muted);
  margin: 12px 0 0; }
.cal .wk .opts label { cursor: pointer; }
.cal .wk .votes, .cal .wk .procs { display: none; margin: 6px 0 2px; }
.cal .wk:has(.t-votes:checked) .votes, .cal .wk:has(.t-procs:checked) .procs { display: block; }
.cal .wk .k { font-size: 11px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--faint);
  margin: 6px 0 2px; }
.cal .wk .dec { padding: 6px 0; border-top: 1px dashed var(--line); font-size: 13px; }
.cal .wk .procs li { margin: 2px 0; font-size: 13px; }
.cal .wk .procs ul { padding-left: 18px; margin: 2px 0; }
.cal .wk .procs .sub { color: var(--muted); font-size: 12px; }
@media (max-width: 640px) {
  .cal .strip { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .cal .grid { grid-template-columns: 1fr; }
}
</style>"""

PERIOD_JS = """<script>
// the toggles above the calendar set every week's toggles; each week's own still works alone (CSS :has)
document.querySelectorAll('.cal .tools input').forEach(t => t.addEventListener('change', () => {
  document.querySelectorAll(`.cal .wk input.${t.dataset.for}`).forEach(x => { x.checked = t.checked; });
}));
</script>"""


def _strip(year: str, weeks: list[str]) -> str:
    """One year as twelve months, each with the ISO weeks whose Monday falls in it; a sitting week links its card."""
    sitting = set(weeks)
    months: dict[int, list[str]] = defaultdict(list)
    day = dt.date.fromisocalendar(int(year), 1, 1)
    while day.year <= int(year):
        if day.year == int(year):
            y, w, _ = day.isocalendar()
            months[day.month].append(f"{y}-W{w:02d}")
        day += dt.timedelta(days=7)
    cells = []
    for m in range(1, 13):
        ws = "".join(f'<a href="#{wk}" title="{e(week_label(wk))}">{int(wk[-2:])}</a>' if wk in sitting
                     else f"<span>{int(wk[-2:])}</span>" for wk in months[m])  # fmt: skip
        cells.append(f'<div class="m"><b>{MONTHS[m - 1][:3]}</b>{ws}</div>')
    return f'<div class="strip" aria-label="Sitzungswochen {e(year)}">{"".join(cells)}</div>'


def week_card(week: str, ss: list[dict], decided: dict[str, list[dict]], moved: dict[str, list[dict]],
              have: set[str]) -> str:  # fmt: skip
    """A sitting week across the page: its name, dates and counts with the way to its page and its
    Themenlandschaft, then its sittings side by side, each with its counts, its longest debate, and its Abstimmungen
    and Vorgänge behind the week's toggles."""
    n_speeches = sum(len(i["speeches"]) for s in ss for i in s["items"])
    sits, k_votes, k_procs = [], 0, 0
    for s in ss:
        ds = decided.get(s["id"], [])
        ps = [x for x in moved.get(s["id"], []) if x["id"] in have]
        k_votes += len(ds)
        k_procs += len(ps)
        votes = "".join(facts.decision(d, "../", when=False, agenda=True) for d in ds)
        procs = "".join(f'<li><a href="../{e(urls.vorgang(x["id"]))}">{e(x["title"])}</a> '
                        f'<span class="sub">{e(", ".join(x["what"]))}</span></li>' for x in ps)  # fmt: skip
        day = WEEKDAYS[dt.date.fromisoformat(s["date"]).weekday()]
        k_sp = sum(len(i["speeches"]) for i in s["items"])
        counts = "".join(f"<span><b>{n(v)}</b>{label}</span>" for v, label in (
            (len(s["items"]), "TOPs"), (k_sp, "Reden"), (len(ds), "Beschlüsse")))  # fmt: skip
        # the longest debate: the questions of the Befragung count as speeches but are not one
        debates = [i for i in s["items"] if not (i["title"] or "").startswith(("Befragung der Bundesregierung",
                                                                                 "Fragestunde"))]  # fmt: skip
        top = max(debates, key=lambda i: len(i["speeches"]), default=None)
        longest = ""
        if top and len(top["speeches"]) > 1:
            title = data.excerpt((top["title"] or "").split("|")[0].strip(), 110)
            longest = (f'<span class="lg"><span class="k">Die meisten Reden ({n(len(top["speeches"]))})</span>'
                       f'<a href="{e(s["page"])}.html#top-{top["position"]}">{e(title)}</a></span>')  # fmt: skip
        sits.append(
            f'<div class="sitc"><span class="sd">{e(day)}, {short_date(s["date"])}</span>'
            f'<a class="sno" href="{e(s["page"])}.html">{s["number"]}. Sitzung</a><span class="sk">{counts}</span>'
            + longest
            + (f'<div class="votes"><div class="k">Abstimmungen</div>{votes}</div>' if ds else "")
            + (f'<div class="procs"><div class="k">Vorgänge</div><ul>{procs}</ul></div>' if ps else "")
            + "</div>"
        )
    opts = []
    if k_votes:
        opts.append(f'<label><input type="checkbox" class="t-votes"> Abstimmungen zeigen ({n(k_votes)})</label>')
    if k_procs:
        opts.append(f'<label><input type="checkbox" class="t-procs"> Vorgänge zeigen ({n(k_procs)})</label>')
    pills = (f'<span class="utag">{plural(len(ss), "Sitzung", "Sitzungen")}</span>'
             f'<span class="utag">{plural(n_speeches, "Rede", "Reden")}</span>'
             f'<span class="utag">{plural(k_votes, "Beschluss", "Beschlüsse")}</span>'
             + (f'<span class="utag">{n(k_procs)} Vorgänge weiter</span>' if k_procs else ""))  # fmt: skip
    return (
        f'<section class="wk" id="{e(week)}"><div class="wk-h"><div class="wk-t">'
        f'<h3><a href="../{e(urls.week(week))}">{e(week_label(week))}</a></h3>'
        f'<div class="dates">{short(ss[0]["date"])[:6]} – {short(ss[-1]["date"])}</div>'
        f'<div class="utags">{pills}</div></div>'
        f'<div class="wk-go"><a class="wk-btn" href="../{e(urls.week(week))}">Die Sitzungswoche →</a>'
        f'<a class="wk-btn rl" href="{LANDSCAPE}{e(week)}.html">Themenlandschaft →</a></div></div>'
        f'<div class="sitcs">{"".join(sits)}</div>'
        + (f'<div class="opts">{"".join(opts)}</div>' if opts else "")
        + "</section>"
    )


def period_page(sittings: list[dict], decided: list[dict], moved: dict[str, list[dict]], have: set[str]) -> str:
    """The Wahlperiode (D18) as a calendar of its sitting weeks, newest first (D29)."""
    by_sitting: dict[str, list[dict]] = defaultdict(list)
    for d in sorted(decided, key=lambda d: d["order"]):
        if d["sitting"]:
            by_sitting[d["sitting"]].append(d)
    weeks = group(sittings)
    years: dict[str, list[str]] = defaultdict(list)
    for wk in weeks:
        years[wk[:4]].append(wk)
    parts = []
    for year, wks in years.items():
        months: dict[int, list[str]] = defaultdict(list)  # a week sits in the month of its first sitting
        for wk in wks:
            months[int(weeks[wk][0]["date"][5:7])].append(wk)
        chapters = "".join(
            f'<h3 class="mon" id="m-{e(year)}-{m:02d}">{MONTHS[m - 1]} <span class="n">'
            f"{plural(len(ws), 'Sitzungswoche', 'Sitzungswochen')}</span></h3>"
            f'<div class="grid">{"".join(week_card(wk, weeks[wk], by_sitting, moved, have) for wk in ws)}</div>'
            for m, ws in months.items()
        )
        k_sit = sum(len(weeks[wk]) for wk in wks)
        parts.append(f'<section class="yr" id="j-{e(year)}"><h2 class="year">{e(year)} <span class="n">'
                     f"{plural(len(wks), 'Sitzungswoche', 'Sitzungswochen')} · {plural(k_sit, 'Sitzung', 'Sitzungen')}"
                     f"</span></h2>{_strip(year, wks)}{chapters}</section>")  # fmt: skip
    tools = ('<div class="tools"><span class="faint">In allen Wochen zeigen:</span>'
             '<label><input type="checkbox" data-for="t-votes"> Abstimmungen</label>'
             '<label><input type="checkbox" data-for="t-procs"> Vorgänge</label></div>')  # fmt: skip
    first = e(long_date(sittings[0]["date"])) if sittings else ""
    body = (
        subtabs("../", SITTING_TABS, "calendar")
        + f'<h1>21. Wahlperiode</h1><p class="lead">{n(len(sittings))} Sitzungen in {n(len(weeks))} Sitzungswochen '
        f"seit {first}, die neueste zuerst. Jede Woche mit ihren Sitzungen; darunter lassen sich je Sitzung die "
        "Abstimmungen und die Vorgänge zeigen, die an dem Tag weitergekommen sind. Jede Sitzung führt zu ihrer "
        "Tagesordnung mit Reden und Beschlüssen, jede Woche zu ihrer Seite. Vorgänge erstrecken sich über viele "
        'Wochen und haben eigene Seiten: <a href="../vorgaenge/index.html">Vorgänge</a>. '
        '<a href="../woche/feed.xml">Die Woche im Bundestag als Feed (Atom)</a></p>'
        f'<div class="cal">{tools}{"".join(parts)}</div><footer>{FOOTER}</footer>{PERIOD_JS}'
    )
    return shell(root="../", kind="p-sittings", active="sittings", title="Sitzungen des Bundestages",
                 desc="Alle Sitzungswochen und Sitzungen des 21. Deutschen Bundestages als Kalender, mit Abstimmungen "
                      "und Vorgängen.", body=body, data={"kind": "sittings"},
                 head=PERIOD_STYLE + ('<script src="../parliament.js"></script>' if decided else ""))  # fmt: skip
