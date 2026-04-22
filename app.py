"""Translation Alignment Viewer — Flask app."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from flask import Flask, abort, render_template

from translation_core.alignment import AlignmentStore
from translation_core.corpora import CorpusRegistry
from translation_core.rendering import render_tokens_html

app = Flask(__name__)

# --- Globals ---
_i18n: dict = {}
_corpora: CorpusRegistry | None = None
_alignments: AlignmentStore | None = None
_initialized = False
_init_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# (id, label, script direction)
TRADITIONS = [
    ("greek_nt", "Greek NT", "ltr"),
    ("peshitta", "Peshitta",  "rtl"),
    ("vulgate",  "Vulgate",   "ltr"),
]

CORPUS_FILES = {
    "greek_nt": "greek_nt.csv",
    "peshitta": "peshitta_nt.csv",
    "vulgate":  "vulgate.csv",
}


def _neighbor(chapter: int, verse: int, direction: int) -> tuple[int, int] | None:
    """Return (chapter, verse) of the neighbor in the given direction (+1 or -1).

    Uses the Greek NT corpus as the master reference for which verses exist.
    """
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
    else:
        if verse > 1 and master.has_verse("Mark", chapter, verse - 1):
            return (chapter, verse - 1)
        if chapter > 1:
            verses = master.verses_in_chapter("Mark", chapter - 1)
            if verses:
                return (chapter - 1, verses[-1])
        return None


def _init() -> None:
    global _i18n, _corpora, _alignments, _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        i18n_path = DATA_DIR / "i18n.json"
        if i18n_path.exists():
            _i18n = json.loads(i18n_path.read_text(encoding="utf-8"))

        _corpora = CorpusRegistry()
        for tid, filename in CORPUS_FILES.items():
            csv_path = DATA_DIR / "corpora" / filename
            if csv_path.exists():
                label = dict((t[0], t[1]) for t in TRADITIONS)[tid]
                _corpora.add(tid, label, csv_path)

        _alignments = AlignmentStore(root=DATA_DIR / "alignments")
        _initialized = True


def _t(key: str, lang: str = "en") -> str:
    return _i18n.get(lang, {}).get(key, key)


@app.before_request
def _ensure_init() -> None:
    _init()


@app.context_processor
def _inject_helpers() -> dict:
    return {"t": _t, "traditions": TRADITIONS}


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/mark/<int:chapter>/<int:verse>")
def viewer(chapter: int, verse: int):
    alignment = _alignments.get("Mark", chapter, verse)
    alignment_pending = False
    if alignment is None:
        alignment = _build_fallback(chapter, verse)
        if alignment is None:
            abort(404)
        alignment_pending = True
    prev_v = _neighbor(chapter, verse, -1)
    next_v = _neighbor(chapter, verse, +1)
    return render_template(
        "viewer.html",
        alignment=alignment,
        alignment_pending=alignment_pending,
        chapter=chapter,
        verse=verse,
        prev=prev_v,
        next=next_v,
        render_tokens_html=render_tokens_html,
    )


@app.route("/partials/verse/mark/<int:chapter>/<int:verse>")
def viewer_partial(chapter: int, verse: int):
    alignment = _alignments.get("Mark", chapter, verse)
    alignment_pending = False
    if alignment is None:
        alignment = _build_fallback(chapter, verse)
        if alignment is None:
            abort(404)
        alignment_pending = True
    prev_v = _neighbor(chapter, verse, -1)
    next_v = _neighbor(chapter, verse, +1)
    return render_template(
        "_verse.html",
        alignment=alignment,
        alignment_pending=alignment_pending,
        chapter=chapter,
        verse=verse,
        prev=prev_v,
        next=next_v,
        render_tokens_html=render_tokens_html,
    )


def _build_fallback(chapter: int, verse: int) -> dict | None:
    """Raw-text-only alignment shape when no alignment JSON exists for this verse."""
    traditions: dict[str, dict] = {}
    any_text = False
    for tid, _label, _dir in TRADITIONS:
        try:
            corpus = _corpora.get(tid)
        except KeyError:
            traditions[tid] = {"absent": True}
            continue
        text = corpus.get("Mark", chapter, verse)
        if text is None:
            traditions[tid] = {"absent": True}
        else:
            traditions[tid] = {"tokens": text.split()}
            any_text = True
    if not any_text:
        return None
    return {
        "ref": f"Mark {chapter}:{verse}",
        "chapter": chapter,
        "verse": verse,
        "traditions": traditions,
        "alignment": [],
        "meta": {
            "generated_by": "fallback",
            "generated_at": "",
            "confidence": 0.0,
            "schema_version": 1,
        },
    }


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5020)))
