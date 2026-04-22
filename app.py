"""Translation Alignment Viewer — Flask app (designer shell + our data)."""
from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

from translation_core.alignment import AlignmentStore
from translation_core.converter import convert_alignment_to_verse
from translation_core.corpora import CorpusRegistry
from translation_core.enrichment import GreekEnrichment, PeshittaEnrichment

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

# --- Globals ---
_corpora: CorpusRegistry | None = None
_alignments: AlignmentStore | None = None
_greek_enrichment: GreekEnrichment | None = None
_peshitta_enrichment: PeshittaEnrichment | None = None
_pericopes: dict = {}
_web_map: dict[str, str] = {}  # ref -> English text
_initialized = False
_init_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CORPUS_FILES = {
    "greek_nt": "greek_nt.csv",
    "peshitta": "peshitta_nt.csv",
    "vulgate":  "vulgate.csv",
}


def _init() -> None:
    global _corpora, _alignments, _greek_enrichment, _peshitta_enrichment
    global _pericopes, _web_map, _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        _corpora = CorpusRegistry()
        for tid, filename in CORPUS_FILES.items():
            csv_path = DATA_DIR / "corpora" / filename
            if csv_path.exists():
                _corpora.add(tid, tid.title(), csv_path)
        _alignments = AlignmentStore(root=DATA_DIR / "alignments")
        _greek_enrichment = GreekEnrichment(DATA_DIR / "enrichment" / "greek_strong.json")
        _peshitta_enrichment = PeshittaEnrichment(DATA_DIR / "enrichment" / "peshitta_roots.json")

        pp = DATA_DIR / "pericopes.json"
        if pp.exists():
            _pericopes = json.loads(pp.read_text(encoding="utf-8"))

        web_path = DATA_DIR / "corpora" / "web.csv"
        if web_path.exists():
            with web_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    _web_map[row["reference"]] = row["text"]

        _initialized = True


@app.before_request
def _ensure_init() -> None:
    _init()


# --- Jinja globals (expected by designer templates) ---

def build_grid(verse: dict) -> list[dict]:
    """Build alignment rows keyed by align-id, in primary-witness (Greek) order."""
    rows: list[dict] = []
    by_id: dict[str, dict] = {}
    witness_ids = [w["id"] for w in verse["witnesses"]]
    primary = next((w for w in verse["witnesses"] if w["id"] == "grk"), verse["witnesses"][0])
    for tok in primary["tokens"]:
        a = tok.get("a")
        if a and a not in by_id:
            row = {"id": a, "cells": {wid: [] for wid in witness_ids}}
            by_id[a] = row
            rows.append(row)
    for w in verse["witnesses"]:
        for tok in w["tokens"]:
            a = tok.get("a")
            if a and a not in by_id:
                row = {"id": a, "cells": {wid: [] for wid in witness_ids}}
                by_id[a] = row
                rows.append(row)
    for w in verse["witnesses"]:
        last = None
        for tok in w["tokens"]:
            a = tok.get("a")
            if a:
                last = by_id[a]
                last["cells"][w["id"]].append(tok)
            elif last is not None:
                last["cells"][w["id"]].append(tok)
            elif rows:
                rows[0]["cells"][w["id"]].append(tok)
    return rows


def verse_stats(verse: dict, grid: list[dict]) -> dict:
    total = len(grid)
    all_three = sum(
        1 for r in grid
        if any(t.get("a") for t in r["cells"].get("grk", []))
        and any(t.get("a") for t in r["cells"].get("syr", []))
        and any(t.get("a") for t in r["cells"].get("vul", []))
    )
    variants = len(verse.get("variants", []))
    major = sum(1 for v in verse.get("variants", []) if "major" in v.get("classes", []))
    return {"total": total, "all_three": all_three, "variants": variants, "major": major}


app.jinja_env.globals["build_grid"] = build_grid
app.jinja_env.globals["verse_stats"] = verse_stats


# --- Neighbor lookup (mark-only for MVP) ---
def _neighbor(chapter: int, verse: int, direction: int) -> tuple[int, int] | None:
    try:
        master = _corpora.get("greek_nt")
    except KeyError:
        return None
    if direction == +1:
        if master.has_verse("Mark", chapter, verse + 1):
            return (chapter, verse + 1)
        if master.has_verse("Mark", chapter + 1, 1):
            return (chapter + 1, 1)
        return None
    if verse > 1 and master.has_verse("Mark", chapter, verse - 1):
        return (chapter, verse - 1)
    if chapter > 1:
        vs = master.verses_in_chapter("Mark", chapter - 1)
        if vs:
            return (chapter - 1, vs[-1])
    return None


def _load_verse(book: str, chapter: int, verse: int) -> dict | None:
    book_title = book.title()  # "Mark"
    alignment = _alignments.get(book_title, chapter, verse)
    if alignment is None:
        # Fallback: build a text-only alignment from corpora
        alignment = _fallback_alignment(book_title, chapter, verse)
        if alignment is None:
            return None
    # Greek per-token glosses from STEP
    greek_glosses: dict[int, str] = {}
    if _greek_enrichment is not None:
        entries = _greek_enrichment._data.get(f"{book_title} {chapter}:{verse}", [])
        for e in entries:
            if e.get("gloss"):
                greek_glosses[e["token_idx"]] = e["gloss"]
    prev_cv = _neighbor(chapter, verse, -1)
    next_cv = _neighbor(chapter, verse, +1)
    gloss_en = _web_map.get(f"{book_title} {chapter}:{verse}")
    return convert_alignment_to_verse(
        alignment,
        book=book_title,
        book_lower=book.lower(),
        prev_cv=prev_cv,
        next_cv=next_cv,
        pericopes=_pericopes,
        testament="New Testament",
        gloss_en=gloss_en,
        greek_glosses=greek_glosses,
    )


def _fallback_alignment(book: str, chapter: int, verse: int) -> dict | None:
    """If no alignment JSON on disk, build a pass-through with no groups."""
    traditions: dict[str, dict] = {}
    any_text = False
    for tid in ("greek_nt", "peshitta", "vulgate"):
        try:
            c = _corpora.get(tid)
        except KeyError:
            traditions[tid] = {"absent": True}
            continue
        text = c.get(book, chapter, verse)
        if text is None:
            traditions[tid] = {"absent": True}
        else:
            traditions[tid] = {"tokens": text.split()}
            any_text = True
    if not any_text:
        return None
    return {
        "ref": f"{book} {chapter}:{verse}", "chapter": chapter, "verse": verse,
        "traditions": traditions,
        "alignment": [],
        "meta": {"generated_by": "fallback", "generated_at": "",
                 "confidence": 0.0, "schema_version": 1},
    }


# --- Routes ---

@app.route("/")
def index():
    return redirect(url_for("verse", book="mark", chapter=1, verse=1))


@app.route("/verse/<book>/<int:chapter>/<int:verse>")
def verse(book: str, chapter: int, verse: int):
    data = _load_verse(book, chapter, verse)
    if data is None:
        abort(404)
    view = request.args.get("view", "interlinear")
    if view not in ("parallel", "interlinear", "apparatus"):
        view = "parallel"
    theme = request.args.get("theme", "light")
    show_rail = request.args.get("rail", "1") != "0"
    open_variant = request.args.get("variant")
    return render_template(
        "verse.html", verse=data, view=view, theme=theme,
        show_rail=show_rail, open_variant=open_variant,
        book_index=_book_index(book.title()),
    )


def _book_index(book: str) -> dict[int, list[int]]:
    """Return {chapter_number: [verse_numbers]} for the given book.

    Used by the verse-jump selector in the topbar.
    """
    try:
        master = _corpora.get("greek_nt")
    except KeyError:
        return {}
    result: dict[int, list[int]] = {}
    for ch in range(1, 17):   # Mark has 16 chapters; adjust when scope expands
        vs = master.verses_in_chapter(book, ch)
        if vs:
            result[ch] = vs
    return result


@app.route("/verse/<book>/<int:chapter>/<int:verse>/partial/<view>")
def verse_partial(book: str, chapter: int, verse: int, view: str):
    data = _load_verse(book, chapter, verse)
    if data is None:
        abort(404)
    if view == "parallel":
        return render_template("_alignment_grid.html", verse=data)
    if view == "interlinear":
        return render_template("_interlinear.html", verse=data)
    if view == "apparatus":
        return render_template(
            "_apparatus.html", verse=data,
            open_variant=request.args.get("variant"),
        )
    abort(404)


# --- Legacy redirect ---
@app.route("/mark/<int:chapter>/<int:verse>")
def legacy_mark(chapter: int, verse: int):
    return redirect(url_for("verse", book="mark", chapter=chapter, verse=verse), code=301)


# --- Tooltip routes (unchanged, preserved) ---
@app.route("/tooltip/greek/<int:chapter>/<int:verse>/<int:token_idx>")
def tooltip_greek(chapter: int, verse: int, token_idx: int):
    entry = _greek_enrichment.lookup("Mark", chapter, verse, token_idx)
    if entry is None:
        return ("", 404)
    return render_template("_tooltip_greek.html", entry=entry)


@app.route("/tooltip/peshitta/<int:chapter>/<int:verse>/<int:token_idx>")
def tooltip_peshitta(chapter: int, verse: int, token_idx: int):
    entry = _peshitta_enrichment.lookup("Mark", chapter, verse, token_idx)
    if entry is None:
        return ("", 404)
    return render_template("_tooltip_peshitta.html", entry=entry)


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5020)))
