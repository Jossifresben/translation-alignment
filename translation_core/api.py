"""Polyglot Concordance — Public API v1.

Read-only JSON endpoints exposing the alignment data, the converted-verse
dict, the search index, and the corpus manifest. All endpoints are
language-neutral (locale belongs to the UI, not the data) and CORS-open
(public, CC BY data — safe to fetch from any origin).

See `docs/superpowers/specs/2026-04-27-api-v1-design.md` for the design.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from translation_core.openapi import OPENAPI_SPEC

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

API_VERSION = "v1"
SUPPORTED_BOOKS = ("mark",)
SEARCH_LIMIT_MAX = 100
SEARCH_LIMIT_DEFAULT = 25


# --------------------------------------------------------------- Headers

@api_v1.after_request
def _apply_api_headers(response):
    """Apply CORS + Cache-Control headers to every API response."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    if response.status_code == 200:
        # Search results are query-keyed and may evolve; shorter TTL.
        if request.path == "/api/v1/search":
            response.headers["Cache-Control"] = "public, max-age=300"
        elif request.path == "/api/v1/":
            # The HTML index page — no aggressive caching needed
            response.headers["Cache-Control"] = "public, max-age=3600"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# --------------------------------------------------------------- Helpers

def _error(code: str, message: str, status: int):
    """Return a JSON error response with the standard envelope."""
    return jsonify({"error": {"code": code, "message": message}}), status


def _normalize_book(book: str) -> str | None:
    """Lowercase the book parameter; return None if unsupported."""
    book_lower = (book or "").lower()
    if book_lower not in SUPPORTED_BOOKS:
        return None
    return book_lower


# --------------------------------------------------------------- Endpoints

@api_v1.route("/alignment/<book>/<int:chapter>/<int:verse>")
def alignment(book, chapter, verse):
    """Return the canonical on-disk alignment JSON for one verse."""
    # Module-level access (not `from app import ...`) so we always read the
    # current value of the global, even on cold start before `_init()` ran.
    import app as _app

    _app._init()
    book_lower = _normalize_book(book)
    if book_lower is None:
        return _error("book_not_found", f"Book '{book}' is not in the corpus", 404)

    book_title = book_lower.title()
    data = _app._alignments.get(book_title, chapter, verse)
    if data is None:
        return _error(
            "alignment_not_found",
            f"No alignment for {book_title} {chapter}:{verse}",
            404,
        )

    return jsonify({"api_version": API_VERSION, **data})


@api_v1.route("/verse/<book>/<int:chapter>/<int:verse>")
def verse_endpoint(book, chapter, verse):
    """Return the converted verse dict (template-shape: witnesses, variants, gloss_map)."""
    import app as _app

    _app._init()
    book_lower = _normalize_book(book)
    if book_lower is None:
        return _error("book_not_found", f"Book '{book}' is not in the corpus", 404)

    data = _app._load_verse(book_lower, chapter, verse)
    if data is None:
        return _error(
            "verse_not_found",
            f"No verse {book_lower.title()} {chapter}:{verse}",
            404,
        )

    return jsonify({"api_version": API_VERSION, **data})


@api_v1.route("/search")
def search():
    """Verse-level search across all witnesses + variant types."""
    import app as _app
    import re

    # Lazy build of the search index (mirrors the existing /search route).
    global _api_search_index_cache
    try:
        idx = _api_search_index_cache  # noqa: F821
    except NameError:
        idx = None
    if idx is None:
        idx = _app._build_search_index()
        globals()["_api_search_index_cache"] = idx

    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit") or SEARCH_LIMIT_DEFAULT)
    except (TypeError, ValueError):
        return _error("bad_request", "limit must be an integer", 400)
    limit = max(1, min(limit, SEARCH_LIMIT_MAX))

    if not q:
        return jsonify({
            "api_version": API_VERSION,
            "query": q,
            "count": 0,
            "items": [],
        })

    # Reference jump (e.g. "13:14")
    m = re.match(r"^(\d+):(\d+)$", q)
    if m:
        ch, v = int(m.group(1)), int(m.group(2))
        for entry in idx:
            if entry["chapter"] == ch and entry["verse"] == v:
                items = [{
                    "ref": entry["ref"],
                    "chapter": ch,
                    "verse": v,
                    "snippet": entry["greek"][:120],
                    "kind": "reference",
                    "matched_in": ["reference"],
                }]
                return jsonify({
                    "api_version": API_VERSION,
                    "query": q,
                    "count": 1,
                    "items": items,
                })
        return jsonify({
            "api_version": API_VERSION, "query": q, "count": 0, "items": [],
        })

    q_low = q.lower()
    items: list[dict] = []
    for entry in idx:
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
            items.append({
                "ref": entry["ref"],
                "chapter": entry["chapter"],
                "verse": entry["verse"],
                "snippet": snippets[0] if snippets else entry["greek"][:120],
                "kind": kinds[0],
                "matched_in": kinds,
            })
            if len(items) >= limit:
                break

    return jsonify({
        "api_version": API_VERSION,
        "query": q,
        "count": len(items),
        "items": items,
    })


@api_v1.route("/manifest")
def manifest():
    """Corpus-level metadata: books, witnesses, gloss editions, schema."""
    import app as _app
    import json
    from pathlib import Path

    _app._init()

    # Build the books list with verse enumeration
    books_out = []
    try:
        master = _app._corpora.get("greek_nt")
    except (KeyError, AttributeError):
        master = None
    if master is not None:
        verses: list[list[int]] = []
        for ch in range(1, 17):
            for v in master.verses_in_chapter("Mark", ch):
                verses.append([ch, v])
        books_out.append({
            "id": "mark",
            "name": "Mark",
            "testament": "New Testament",
            "chapters": 16,
            "verse_count": len(verses),
            "verses": verses,
        })

    # Benchmark metadata, if present on disk
    benchmark = None
    bench_path = Path(__file__).resolve().parent.parent / "data" / "benchmarks" / "berean_preflight.json"
    if bench_path.exists():
        try:
            b = json.loads(bench_path.read_text(encoding="utf-8"))
            benchmark = {
                "name": "Berean Interlinear Bible",
                "task": "Greek → English token alignment",
                "verses": b.get("sample_size"),
                "agreement_rate": b.get("agreement_rate"),
            }
        except Exception:
            benchmark = None

    return jsonify({
        "api_version": API_VERSION,
        "project": "Polyglot Concordance",
        "description": (
            "A concordance initiative with alignment to the word level — "
            "Mark across Greek NT, Syriac Peshitta, and Latin Clementine "
            "Vulgate, with AI-generated alignment and apparatus annotations "
            "on every divergence. A machine-generated alignment draft, "
            "intended as a starting point for scholar review rather than "
            "as an authoritative critical edition."
        ),
        "license": (
            "Code: open-source (intended). Derived alignment JSON: CC BY 4.0 "
            "+ public domain mix; redistribute with attribution."
        ),
        "schema_version": 1,
        "books": books_out,
        "witnesses": [
            {
                "id": "greek_nt", "sigil": "𝔊", "name": "Greek NT",
                "script": "grc", "dir": "ltr",
                "source": "STEP Bible TAGNT (Tyndale House Cambridge)",
            },
            {
                "id": "peshitta", "sigil": "ℙ", "name": "Syriac Peshitta",
                "script": "syr", "dir": "rtl",
                "source": "Aramaic Root Atlas corpus",
            },
            {
                "id": "vulgate", "sigil": "𝔙", "name": "Clementine Vulgate",
                "script": "lat", "dir": "ltr",
                "source": "seven1m/open-bibles (USFX)",
            },
        ],
        "verse_glosses": [
            {"lang": "en", "name": "English",
             "edition": "World English Bible (WEB), public domain"},
            {"lang": "es", "name": "Español",
             "edition": "Reina-Valera 1909, public domain"},
            {"lang": "zh-Hans", "name": "简体中文",
             "edition": "Chinese Union Version 1919 (Simplified), public domain"},
            {"lang": "zh-Hant", "name": "繁體中文",
             "edition": "Chinese Union Version 1919 (Traditional), public domain"},
        ],
        "variant_verdicts": ["aligned", "minor", "major", "omitted", "added"],
        "variant_types": [
            "agreement", "expansion", "omission", "substitution", "harmonisation",
            "word-order", "construction", "idiom", "punctuation", "grammar",
            "lexical", "gloss",
        ],
        "alignment_generation": {
            "model": "claude-sonnet-4-5",
            "via": "Anthropic Messages Batch API",
            "benchmark": benchmark,
        },
        "endpoints": [
            "/api/v1/alignment/{book}/{chapter}/{verse}",
            "/api/v1/verse/{book}/{chapter}/{verse}",
            "/api/v1/search?q={query}&limit={n}",
            "/api/v1/manifest",
            "/api/v1/openapi.json",
        ],
    })


@api_v1.route("/openapi.json")
def openapi():
    """OpenAPI 3.0 spec for v1 endpoints."""
    return jsonify(OPENAPI_SPEC)


@api_v1.route("/")
def index():
    """Landing page for the API root — links + curl example."""
    return render_template("api/index.html")
