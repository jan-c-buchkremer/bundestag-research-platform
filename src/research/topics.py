"""Topics (docs/plan.md section 11.6, D19): `themen/index.html` and `themen/<theme id>.html`, one page per period
theme of the Themenlandschaft, read from `speech_themes.json` (LANDSCAPE_THEMES, as debate.py). Built only when the
file is set; the landscape owns topic modelling (D3).

Week clusters are not entities, their ids change with every rebuild of a week. The period theme's id is not stable
either: the landscape numbers themes by size and recomputes the model whenever the set of speeches changes. So the
pages say that their address may change, and no stubs are written for them; stable ids are a landscape requirement.
A topic page is an entity page: the theme's speeches (facts.py), the fractions that spoke on it, and the Vorgänge
whose debates they belong to."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from research import facts, urls
from research.ui import (
    FOOTER,
    LANDSCAPE,
    ORDER,
    TOKEN,
    crumbs,
    dot,
    e,
    entity_header,
    facet,
    frac_link,
    fraction_order,
    long_date,
    method_note,
    n,
    shell,
)

SPEECHES = 100  # newest speeches of a theme in the page (a theme holds a few hundred)
NOTE = ("Themen stammen aus der Themenlandschaft, die alle Reden der Wahlperiode nach Ähnlichkeit gruppiert. Die "
        "Nummer eines Themas kann sich ändern, wenn neue Sitzungswochen hinzukommen. Links auf diese Seite sind "
        "deshalb nicht dauerhaft.")  # fmt: skip
# the Radar method note (docs/architecture.md): how the themes were made and what they can and cannot tell
METHOD = ("Jede Rede der Wahlperiode als Embedding (multilingual-e5-base), gruppiert mit UMAP und HDBSCAN, benannt "
          "nach typischen Wörtern (c-TF-IDF). Ein Thema zeigt, dass Reden ähnliche Wörter benutzen. Über die "
          "vertretenen Positionen sagt es nichts. Mit neuen Sitzungswochen können sich Themen und ihre Namen "
          "ändern.")  # fmt: skip


def by_theme(themes: dict[str, dict], speeches: list[dict]) -> dict[int, dict]:
    """{theme id: {"id", "label", "speeches"}} for the speeches with a card, oldest first."""
    out: dict[int, dict] = {}
    for sp in speeches:
        t = themes.get(sp["id"])
        if t is None or t.get("theme_id") is None:
            continue
        th = out.setdefault(t["theme_id"], {"id": t["theme_id"], "label": t["label"], "speeches": []})
        th["speeches"].append(sp)
    return dict(sorted(out.items(), key=lambda kv: -len(kv[1]["speeches"])))


def topic_page(th: dict, procedures: dict[str, dict]) -> str:
    sps = th["speeches"]
    newest = sorted(sps, key=lambda s: (s["date"], s["id"]), reverse=True)[:SPEECHES]
    more = (f'<p class="explain">Die neuesten {n(len(newest))} von {n(len(sps))}. Alle: '
            f'<a class="rl" href="{LANDSCAPE}index.html#thema={e(th["id"])}">das Thema in der Themenlandschaft</a>.</p>'
            if len(sps) > len(newest) else "")  # fmt: skip
    per = Counter(s.get("fraction") or "ohne Fraktion" for s in sps)
    rows = "".join(f'<tr><td>{dot(f)} {frac_link(f)}</td><td class="num">{n(k)}</td></tr>'
                   for f, k in sorted(per.items(), key=lambda kv: fraction_order(kv[0])))  # fmt: skip
    vs = Counter(v for s in sps for v in procedures.get(s["id"], []))
    vlinks = "".join(f'<li><a href="../{e(urls.vorgang(v))}">{e(title)}</a> <span class="faint">'
                     f"{n(k)} {'Rede' if k == 1 else 'Reden'}</span></li>"
                     for (v, title), k in sorted(vs.items(), key=lambda kv: (-kv[1], kv[0][1])))  # fmt: skip
    body = (
        crumbs(("index.html", "Themen"), (None, th["label"]))
        + entity_header(th["label"], [f"{n(len(sps))} Reden in der 21. Wahlperiode", NOTE],
                        [f'<a class="rl" href="{LANDSCAPE}index.html#thema={e(th["id"])}">In der Themenlandschaft</a>'],
                        when="Thema")
        + facet("fraktionen", "Fraktionen", '<div class="rows"><table class="plenum"><thead><tr><th>Fraktion</th>'
                f"<th>Reden</th></tr></thead><tbody>{rows}</tbody></table></div>", explain="Wie viele Reden zu "
                "diesem Thema aus jeder Fraktion kamen. Größere Fraktionen haben mehr Redezeit.")
        + facet("reden", "Reden", facts.speech_list(newest, "../", "reden", note=more), len(sps))
        + facet("abstimmungen", "Abstimmungen und Beschlüsse",
                f'<ul class="plain">{vlinks}</ul>' if vlinks else "", len(vs), "Ein Thema gilt für Reden, nicht für "
                "Abstimmungen. Die Vorgänge, in deren Beratung die Reden gehalten wurden, führen zu ihren "
                "Abstimmungen.")
        + facet("drucksachen", "Drucksachen", "", explain="Drucksachen haben kein Thema der Themenlandschaft. Das DIP "
                f'ordnet ihre Vorgänge nach <a href="../{urls.SUBJECTS}">Sachgebieten</a>.')
        + method_note(METHOD) + f"<footer>{FOOTER}</footer>"
    )  # fmt: skip
    return shell(root="../", kind="p-topic", active="radar", mode="radar", title=f"Thema: {th['label']}",
                 desc=f"Das Thema „{th['label']}“ im 21. Bundestag: Reden, Fraktionen und Vorgänge.", body=body,
                 data={"kind": "topic", "id": th["id"]}, head='<meta name="robots" content="noindex">')  # fmt: skip


SHOWN = 40  # themes in the overview before "Alle N zeigen"


def mix_bar(sps: list[dict]) -> str:
    """The theme's speeches by fraction as one stacked bar, in the fractions' colours and order."""
    per = Counter(sp.get("fraction") or "ohne Fraktion" for sp in sps)
    total = sum(per.values()) or 1
    parts = "".join(
        f'<i style="width:{100 * k / total:.1f}%;background:var(--{TOKEN.get(f, "reg")})" title="{e(f)}: {n(k)}"></i>'
        for f, k in sorted(per.items(), key=lambda kv: fraction_order(kv[0]))
    )
    return f'<span class="mix" aria-hidden="true">{parts}</span>'  # fmt: skip


def index_page(themes: dict[int, dict]) -> str:
    biggest = max((len(th["speeches"]) for th in themes.values()), default=1)

    def row(th: dict) -> str:
        sps = th["speeches"]
        last = max(sp["date"] for sp in sps)
        return (f'<a class="row th" href="{e(th["id"])}.html"><span class="t"><span class="ti">{e(th["label"])}</span>'
                f'<span class="sub">{mix_bar(sps)}<span>zuletzt am {e(long_date(last))}</span></span></span>'
                f'<span class="l"><b>{n(len(sps))}</b> Reden<span class="size"><i style="width:'
                f'{100 * len(sps) / biggest:.1f}%"></i></span></span></a>')  # fmt: skip

    ths = list(themes.values())
    total = sum(len(th["speeches"]) for th in ths)
    rest = (f'<details class="srest"><summary>Alle {n(len(ths))} Themen zeigen</summary><div class="rows">'
            f'{"".join(row(th) for th in ths[SHOWN:])}</div></details>' if len(ths) > SHOWN else "")  # fmt: skip
    keys = "".join(f'<span class="k"><span class="dot" style="background:var(--{TOKEN[f]})"></span>{e(f)}</span>'
                   for f in ORDER if f in TOKEN)  # fmt: skip
    body = (
        entity_header("Themen der Wahlperiode", [f"{n(len(ths))} Themen aus {n(total)} Reden der 21. Wahlperiode, "
                      "das größte zuerst.", NOTE],
                      [f'<a class="rl" href="{LANDSCAPE}index.html">In der Themenlandschaft</a>'], when="Thema")
        + f'<div class="th-keys"><span>Reden nach Fraktion:</span>{keys}<span class="sz"><span class="size"><i '
        'style="width:60%"></i></span>Größe im Vergleich zum größten Thema</span></div>'
        + f'<div class="rows">{"".join(row(th) for th in ths[:SHOWN])}</div>{rest}'
        + f"{method_note(METHOD)}<footer>{FOOTER}</footer>"
    )  # fmt: skip
    style = """<style>
.p-topics .row.th { grid-template-columns: 1fr 150px; align-items: center; }
.p-topics .row.th .sub { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 4px; }
.p-topics .mix { display: inline-flex; width: 180px; height: 7px; border-radius: 4px; overflow: hidden;
  background: var(--line); }
.p-topics .mix i { display: block; height: 100%; }
.p-topics .row.th .l { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; font-size: 12.5px;
  color: var(--muted); white-space: nowrap; }
.p-topics .row.th .l b { color: var(--text); font-size: 14px; }
.p-topics .size { display: block; width: 120px; height: 5px; border-radius: 3px; background: var(--radar-soft); }
.p-topics .size i { display: block; height: 100%; border-radius: 3px; background: var(--radar); }
.p-topics .th-keys { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: 18px 0 10px;
  font-size: 12px; color: var(--muted); }
.p-topics .th-keys .sz { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; }
.p-topics .th-keys .sz .size { width: 40px; }
.p-topics .th-keys .dot { margin-right: 5px; }
.p-topics .srest > summary { margin-top: 10px; }
@media (max-width: 560px) { .p-topics .row.th { grid-template-columns: 1fr; } .p-topics .row.th .l {
  flex-direction: row; align-items: center; } .p-topics .mix { width: 140px; } }
</style>"""
    return shell(root="../", kind="p-topics", active="radar", mode="radar", title="Themen der Wahlperiode",
                 desc="Die Themen der Reden im 21. Deutschen Bundestag, aus der Themenlandschaft.", body=body,
                 data={"kind": "topics"}, head='<meta name="robots" content="noindex">' + style)  # fmt: skip


def write(out: Path, themes: dict[str, dict], speeches: list[dict], sittings: list[dict]) -> dict[int, dict]:
    """Write themen/ when the landscape's themes are there; returns the themes written (empty without them)."""
    grouped = by_theme(themes, speeches)
    if not grouped:
        return {}
    procedures: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for s in sittings:
        for i in s["items"]:
            for part in [i, *(i.get("sub_items") or [])]:
                for sp in part["speeches"]:
                    procedures[sp["id"]] += [(v["id"], v["title"]) for v in part.get("vorgaenge") or []]
    d = out / "themen"
    d.mkdir(parents=True, exist_ok=True)
    for th in grouped.values():
        (d / f"{th['id']}.html").write_text(topic_page(th, procedures), encoding="utf-8")
    (d / "index.html").write_text(index_page(grouped), encoding="utf-8")
    return grouped
