"""Polyglot Concordance — Flask app (designer shell + our data)."""
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
from translation_core.i18n import SUPPORTED as I18N_SUPPORTED, Translations

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

# --- Globals ---
_corpora: CorpusRegistry | None = None
_alignments: AlignmentStore | None = None
_greek_enrichment: GreekEnrichment | None = None
_peshitta_enrichment: PeshittaEnrichment | None = None
_pericopes: dict = {}
# ref -> per-language verse text. Keys: 'en', 'es', 'zh-Hans', 'zh-Hant'.
_gloss_maps: dict[str, dict[str, str]] = {
    "en": {},
    "es": {},
    "zh-Hans": {},
    "zh-Hant": {},
}
_initialized = False
_init_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TRANSLATIONS_DIR = BASE_DIR / "translations"
_translations = Translations(TRANSLATIONS_DIR)


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Jinja global: resolve a translation key in the current request's lang.

    If kwargs are passed, they're applied to the resolved string via
    str.format() — letting templates inject dynamic values into a
    translated paragraph (e.g. benchmark numbers, percentages) without
    fragmenting the prose into many small keys.

    On format failure (missing placeholder, malformed value), the raw
    string is returned so the page still renders rather than 500ing.
    """
    from flask import g
    current_lang = getattr(g, "lang", lang)
    val = _translations.t(key, current_lang)
    if kwargs:
        try:
            return val.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return val
    return val

CORPUS_FILES = {
    "greek_nt": "greek_nt.csv",
    "peshitta": "peshitta_nt.csv",
    "vulgate":  "vulgate.csv",
}

GLOSS_FILES = {
    "en":      "web.csv",
    "es":      "rv1909.csv",
    "zh-Hans": "cuv_hans.csv",
    "zh-Hant": "cuv_hant.csv",
}


def _init() -> None:
    global _corpora, _alignments, _greek_enrichment, _peshitta_enrichment
    global _pericopes, _initialized
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

        for lang, filename in GLOSS_FILES.items():
            path = DATA_DIR / "corpora" / filename
            if not path.exists():
                continue   # acceptable during incremental rollout
            with path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    _gloss_maps[lang][row["reference"]] = row["text"]

        _initialized = True


LANG_PREFIXES = ("zh-Hans", "zh-Hant", "es")


class _LocalePrefixMiddleware:
    """WSGI middleware: strip /<lang>/ prefix from PATH_INFO, stash lang in environ.

    Runs before Flask's URL routing so that existing routes (`/about`,
    `/verse/...`) match unchanged after the prefix is stripped. The chosen
    language is later surfaced as ``g.lang`` in a before_request hook.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        for lang in LANG_PREFIXES:
            if path == f"/{lang}" or path.startswith(f"/{lang}/"):
                environ["translation_aligner.lang"] = lang
                environ["PATH_INFO"] = path[len(f"/{lang}"):] or "/"
                break
        return self.wsgi_app(environ, start_response)


app.wsgi_app = _LocalePrefixMiddleware(app.wsgi_app)


@app.before_request
def _ensure_init_and_locale():
    _init()
    from flask import g
    # Read the language stashed by the WSGI middleware (if any prefix was stripped)
    g.lang = request.environ.get("translation_aligner.lang", "en")

    # Auto-redirect at bare root only.
    # Three cases:
    #   1. Existing cookie says non-English (es/zh-Hans/zh-Hant) → 302 to that lang
    #   2. No cookie + Accept-Language matches non-English → 302 to that lang, set cookie
    #   3. Otherwise (English cookie, English Accept-Language, etc.) → fall through, render /
    #
    # The g.lang == "en" guard prevents loops — if the user is at /zh-Hans/
    # (which the middleware rewrites to PATH_INFO=/), g.lang is already
    # zh-Hans from the URL prefix, so we won't redirect.
    if request.path == "/" and g.lang == "en":
        cookie_lang = request.cookies.get("lang")
        if cookie_lang in LANG_PREFIXES:
            # User has explicitly chosen a non-English lang earlier; honor it.
            return redirect(f"/{cookie_lang}/", code=302)
        if cookie_lang is None:
            # First visit — try Accept-Language
            from translation_core.i18n import parse_accept_language
            wanted = parse_accept_language(request.headers.get("Accept-Language"))
            if wanted:
                from flask import make_response
                resp = make_response(redirect(f"/{wanted}/", code=302))
                resp.set_cookie("lang", wanted, max_age=60 * 60 * 24 * 365, samesite="Lax")
                return resp
    return None


@app.after_request
def _set_lang_cookie(response):
    """Persist g.lang in a cookie when one is missing.

    Skips redirects (already set above) and skips overwriting existing cookies.
    """
    from flask import g
    if "lang" in request.cookies:
        return response
    if response.status_code in (301, 302, 303, 307, 308):
        return response
    lang = getattr(g, "lang", "en")
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response


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


def i18n_for_js() -> dict[str, str]:
    """Return the subset of translation keys whose path starts with 'js.'.

    This is what gets injected as window.__I18N__ on every page so that
    aligner.js can resolve client-side strings without a fetch roundtrip.
    """
    from flask import g
    lang = getattr(g, "lang", "en")
    en_keys = _translations.keys("en")
    return {k: _translations.t(k, lang) for k in en_keys if k.startswith("js.")}


app.jinja_env.globals["i18n_for_js"] = i18n_for_js


def localized_url_for(endpoint: str, **values) -> str:
    """Like Flask's url_for, but prepends /<lang>/ when g.lang is not 'en'.

    Static assets (anything under /static/) are NEVER prefixed — the
    locale doesn't affect static URLs.
    """
    from flask import g
    base = url_for(endpoint, **values)
    if base.startswith("/static/"):
        return base
    lang = getattr(g, "lang", "en")
    if lang == "en" or lang not in I18N_SUPPORTED:
        return base
    return f"/{lang}{base}"


app.jinja_env.globals["localized_url_for"] = localized_url_for
app.jinja_env.globals["t"] = t
app.jinja_env.globals["supported_langs"] = I18N_SUPPORTED


def canonical_path() -> str:
    """Return the request path stripped of any language prefix.

    Used by base.html to generate hreflang alternate links and by
    sitemap.xml to enumerate localized URLs without duplication.

    For /es/about → /about ; for /verse/mark/1/1 → /verse/mark/1/1.

    Note: the _LocalePrefixMiddleware already strips the prefix from
    PATH_INFO before Flask sees the request, so in practice request.path
    is already the canonical (un-prefixed) path. The defensive scan
    below is a no-op in that case but protects against direct callers.
    """
    path = request.path
    for lang in LANG_PREFIXES:
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            return path[len(f"/{lang}"):] or "/"
    return path


app.jinja_env.globals["canonical_path"] = canonical_path


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
    ref = f"{book_title} {chapter}:{verse}"
    gloss_map = {lang: m.get(ref, "") for lang, m in _gloss_maps.items()}
    gloss_en = gloss_map.get("en") or None  # backward-compat: existing code may still use gloss_en
    return convert_alignment_to_verse(
        alignment,
        book=book_title,
        book_lower=book.lower(),
        prev_cv=prev_cv,
        next_cv=next_cv,
        pericopes=_pericopes,
        testament="New Testament",
        gloss_en=gloss_en,
        gloss_map=gloss_map,
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
    return render_template("home.html",
                           view=None, theme=request.args.get("theme", "light"),
                           show_rail=False, verse=None)


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


@app.route("/about")
def about():
    benchmark_path = DATA_DIR / "benchmarks" / "berean_preflight.json"
    benchmark = None
    if benchmark_path.exists():
        try:
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        except Exception:
            benchmark = None
    return render_template("about.html", benchmark=benchmark,
                            view=None, theme=request.args.get("theme", "light"),
                            show_rail=False, verse=None)


@app.route("/favicon.ico")
def favicon():
    """Browsers request /favicon.ico at the root — serve from static/img."""
    from flask import send_from_directory
    return send_from_directory(
        BASE_DIR / "static" / "img", "favicon.ico", mimetype="image/x-icon"
    )


@app.route("/llms.txt")
def llms_txt():
    """Plain-text overview for LLM crawlers (the emerging llms.txt convention)."""
    from flask import send_from_directory
    return send_from_directory(BASE_DIR, "llms.txt", mimetype="text/plain")


@app.route("/robots.txt")
def robots_txt():
    from flask import send_from_directory
    return send_from_directory(BASE_DIR / "static", "robots.txt", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Localized sitemap with xhtml:link alternates per Google's sitemap spec.

    Each canonical URL is emitted four times (one per language with the
    appropriate path-prefix). Each <url> entry includes <xhtml:link
    rel="alternate" hreflang="..."/> rows pointing at the other three
    so search engines can discover and disambiguate them.
    """
    from flask import Response
    paths: list[str] = ["/", "/about"]
    try:
        master = _corpora.get("greek_nt")
    except KeyError:
        master = None
    if master is not None:
        for ch in range(1, 17):
            for v in master.verses_in_chapter("Mark", ch):
                paths.append(f"/verse/mark/{ch}/{v}")

    base = request.url_root.rstrip("/")
    LANGS = ("en", "es", "zh-Hans", "zh-Hant")

    def url_for_lang(path: str, lang: str) -> str:
        return base + (path if lang == "en" else f"/{lang}{path}")

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
        ' xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path in paths:
        for lang in LANGS:
            out.append("  <url>")
            out.append(f"    <loc>{url_for_lang(path, lang)}</loc>")
            for alt in LANGS:
                out.append(
                    f'    <xhtml:link rel="alternate" hreflang="{alt}" '
                    f'href="{url_for_lang(path, alt)}"/>'
                )
            out.append("  </url>")
    out.append("</urlset>")
    return Response("\n".join(out), mimetype="application/xml")


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


import csv as _csv_search_module  # alias to avoid clashing with any local `csv` name

_SEARCH_INDEX: list[dict] = []   # populated on first /search call


def _build_search_index() -> list[dict]:
    """One-shot index over Mark for the search palette.

    Each entry: {ref, chapter, verse, greek, peshitta, vulgate, english,
                 types (sorted list of variant types)}
    """
    def _load_csv(path: Path) -> dict[tuple[int, int], str]:
        result: dict[tuple[int, int], str] = {}
        if not path.exists():
            return result
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = _csv_search_module.DictReader(f)
            # Detect text column (Peshitta CSV from ARA uses `syriac`, not `text`)
            first = next(reader, None)
            if first is None:
                return result
            text_col = next((c for c in ("text", "syriac", "latin", "hebrew", "greek")
                             if c in first), None)
            if not text_col:
                return result
            rows = [first, *reader]
            for r in rows:
                if r.get("book") == "Mark":
                    result[(int(r["chapter"]), int(r["verse"]))] = r.get(text_col, "")
        return result

    greek    = _load_csv(DATA_DIR / "corpora" / "greek_nt.csv")
    peshitta = _load_csv(DATA_DIR / "corpora" / "peshitta_nt.csv")
    vulgate  = _load_csv(DATA_DIR / "corpora" / "vulgate.csv")
    english  = _load_csv(DATA_DIR / "corpora" / "web.csv")

    index: list[dict] = []
    align_root = DATA_DIR / "alignments" / "mark"
    for (ch, v), g in sorted(greek.items()):
        types: set[str] = set()
        path = align_root / str(ch) / f"{v}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for group in data.get("alignment", []):
                    if group.get("variant") and group["variant"] != "aligned":
                        types.add(group.get("type") or group["variant"])
            except Exception:
                pass
        index.append({
            "ref": f"Mark {ch}:{v}",
            "chapter": ch, "verse": v,
            "greek":    g,
            "peshitta": peshitta.get((ch, v), ""),
            "vulgate":  vulgate.get((ch, v), ""),
            "english":  english.get((ch, v), ""),
            "types":    sorted(types),
        })
    return index


@app.route("/search")
def search():
    global _SEARCH_INDEX
    if not _SEARCH_INDEX:
        _SEARCH_INDEX = _build_search_index()
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 25)
    if not q:
        return {"results": []}
    # Reference jump — "13:14"
    import re as _re
    m = _re.match(r"^(\d+):(\d+)$", q)
    if m:
        ch, v = int(m.group(1)), int(m.group(2))
        for entry in _SEARCH_INDEX:
            if entry["chapter"] == ch and entry["verse"] == v:
                return {"results": [{"ref": entry["ref"],
                                     "chapter": ch, "verse": v,
                                     "snippet": entry["greek"][:120],
                                     "kind": "reference"}]}
        return {"results": []}
    q_low = q.lower()
    out: list[dict] = []
    for entry in _SEARCH_INDEX:
        kinds: list[str] = []
        snippets: list[str] = []
        if q in entry["greek"] or q_low in entry["greek"].lower():
            kinds.append("greek")
            snippets.append(entry["greek"][:160])
        if entry["peshitta"] and q in entry["peshitta"]:
            kinds.append("peshitta")
            snippets.append(entry["peshitta"][:160])
        if entry["vulgate"] and (q in entry["vulgate"] or q_low in entry["vulgate"].lower()):
            kinds.append("vulgate")
            snippets.append(entry["vulgate"][:160])
        if q_low and q_low in entry["english"].lower():
            kinds.append("english")
            snippets.append(entry["english"][:160])
        if any(q_low in t.lower() for t in entry["types"]):
            kinds.append("type")
            snippets.append("type: " + ", ".join(entry["types"]))
        if kinds:
            out.append({
                "ref": entry["ref"],
                "chapter": entry["chapter"],
                "verse": entry["verse"],
                "snippet": snippets[0] if snippets else entry["greek"][:120],
                "kind": kinds[0],
                "matched_in": kinds,
            })
            if len(out) >= limit:
                break
    return {"results": out}


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5020)))
