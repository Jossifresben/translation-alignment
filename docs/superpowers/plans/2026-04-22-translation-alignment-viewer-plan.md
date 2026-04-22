# Translation Alignment Viewer (MVP) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a focus-verse web viewer that displays the Gospel of Mark side-by-side in Greek NT, Peshitta (Syriac), and Clementine Vulgate, with word-level color-coded variant alignment generated offline by Claude.

**Architecture:** Flask + Jinja + htmx (no SPA, no build step). Corpus CSVs + per-verse alignment JSON committed to the repo as the source of truth. Alignment is pre-computed once via Claude Sonnet 4.6 (Batch API) and stored statically — the running app has zero external runtime dependencies. Enrichment layers (Greek Strong's/morph from STEP Bible, Peshitta roots from Aramaic Root Atlas) surface on click as tooltips.

**Tech Stack:** Python 3.11+, Flask, Jinja2, htmx (CDN), pytest, `anthropic` SDK (scripts only), `python-dotenv` (local only). Deployment target: Render.com free tier.

**Spec reference:** `docs/superpowers/specs/2026-04-22-translation-alignment-viewer-design.md`

---

## File structure

New code written by this plan:

```
translation-alignment/
  app.py                                  # Task 4, expanded in Tasks 10, 13, 18, 22
  translation_core/
    __init__.py                           # Task 1
    corpora.py                            # Task 5 (CSV loading + ref-based lookup)
    alignment.py                          # Task 8 (JSON loading + validation + lookup)
    enrichment.py                         # Task 13 (Strong's + root lookup)
    rendering.py                          # Task 9 (verse card HTML macro)
    schema.py                             # Task 7 (alignment JSON schema + validator)
  templates/
    base.html                             # Task 4 (adapted from ARA)
    index.html                            # Task 4
    viewer.html                           # Task 10
    _verse.html                           # Task 10 (htmx partial)
    _tooltip_greek.html                   # Task 13
    _tooltip_peshitta.html                # Task 13
    about.html                            # Task 18
    404.html                              # Task 22
  static/
    style.css                             # Task 4 (copied from ARA + variant styles)
    viewer.js                             # Task 20 (keyboard shortcuts, tooltip wiring)
    fonts/EstrangeloEdessa.woff2          # Task 21 (self-hosted Syriac font)
  data/
    corpora/
      greek_nt.csv                        # Task 3 (built from ARA translations_el.json)
      peshitta_nt.csv                     # Task 3 (copied from ARA)
      vulgate.csv                         # Task 6 (ingested from Clementine source)
    alignments/mark/{ch}/{v}.json         # Task 15 (Claude-generated, ~678 files)
    alignments/_fixtures/                 # Task 7 (hand-crafted examples for tests)
    enrichment/
      greek_strong.json                   # Task 12
      peshitta_roots.json                 # Task 14
    benchmarks/
      berean_preflight.json               # Task 19
    i18n.json                             # Task 4 (copied from ARA, trimmed)
  scripts/
    ingest_vulgate.py                     # Task 6
    extract_step_enrichment.py            # Task 12
    snapshot_ara_roots.py                 # Task 14
    run_berean_benchmark.py               # Task 19
    generate_alignments.py                # Tasks 15, 16, 17
  tests/
    conftest.py                           # Task 1
    test_corpora.py                       # Task 5
    test_schema.py                        # Task 7
    test_alignment.py                     # Task 8
    test_rendering.py                     # Task 9
    test_routes.py                        # Tasks 10, 18, 22
    test_enrichment.py                    # Task 13
    test_ingest_vulgate.py                # Task 6
    fixtures/
      alignment_mark_1_1.json             # Task 7
      vulgate_mark_sample.txt             # Task 6
  docs/superpowers/{specs,plans}/         # Already exist
  known-issues.md                         # Task 17
  QA_LOG.md                               # Task 23
  README.md                               # Task 1
  requirements.txt                        # Task 1
  requirements-dev.txt                    # Task 1
  pyproject.toml                          # Task 1
  render.yaml                             # Task 24
  .env / .env.example / .gitignore        # Already exist (created during brainstorm)
```

**Design discipline:**
- Each `translation_core/` module has one responsibility and is independently testable
- Tests live beside `tests/` parallel to `translation_core/`
- `app.py` is a thin route layer — business logic stays in `translation_core/`
- No module exceeds ~200 lines; split if it grows

---

## Phase 1 — Repo scaffolding (Tasks 1–2)

### Task 1: Initialize the Python project

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `README.md`
- Create: `translation_core/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "translation-alignment"
version = "0.1.0"
description = "Parallel biblical text alignment viewer — MVP (Mark, Greek/Peshitta/Vulgate)"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Create `requirements.txt` (runtime only)**

```
Flask==3.0.3
Jinja2==3.1.4
python-dotenv==1.0.1
```

- [ ] **Step 3: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.2
pytest-cov==5.0.0
anthropic==0.39.0
jsonschema==4.23.0
ruff==0.6.9
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Translation Alignment Viewer (MVP)

Focus-verse web viewer for parallel biblical texts. Pilot scope: Gospel of Mark in Greek NT (SBLGNT) + Peshitta (Syriac) + Clementine Vulgate, with word-level color-coded variant alignment pre-computed by Claude.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY for scripts
pytest                        # run tests
python app.py                 # run local viewer at http://localhost:5000
```

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` for the implementation plan.
```

- [ ] **Step 5: Create empty package files**

```bash
mkdir -p translation_core tests/fixtures
touch translation_core/__init__.py
touch tests/__init__.py
```

Write `tests/conftest.py`:

```python
"""Shared pytest fixtures."""
import os
import sys
from pathlib import Path

# Make the project root importable as a package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
```

- [ ] **Step 6: Verify smoke test**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Expected output: `no tests ran in 0.XXs` (or similar). If pytest errors, fix the config before continuing.

- [ ] **Step 7: Init git and commit**

```bash
git init
git add pyproject.toml requirements.txt requirements-dev.txt README.md translation_core tests .gitignore .env.example
git commit -m "chore: scaffold Python project for translation-alignment MVP"
```

Confirm `.env` was **not** added (check `git status` before and after; `.env` should stay untracked).

---

### Task 2: Create empty directory layout and placeholder data/ tree

**Files:**
- Create: `data/corpora/.gitkeep`
- Create: `data/alignments/mark/.gitkeep`
- Create: `data/alignments/_fixtures/.gitkeep`
- Create: `data/alignments/_quarantine/.gitkeep`
- Create: `data/enrichment/.gitkeep`
- Create: `data/benchmarks/.gitkeep`
- Create: `templates/.gitkeep`
- Create: `static/fonts/.gitkeep`
- Create: `scripts/.gitkeep`

- [ ] **Step 1: Create all directories with .gitkeep markers**

```bash
mkdir -p data/corpora data/alignments/mark data/alignments/_fixtures data/alignments/_quarantine data/enrichment data/benchmarks templates static/fonts scripts
for d in data/corpora data/alignments/mark data/alignments/_fixtures data/alignments/_quarantine data/enrichment data/benchmarks templates static/fonts scripts; do touch "$d/.gitkeep"; done
```

- [ ] **Step 2: Commit**

```bash
git add data templates static scripts
git commit -m "chore: create directory skeleton"
```

---

## Phase 2 — Corpus ingestion (Tasks 3–6)

### Task 3: Build Greek NT + Peshitta NT CSVs from ARA sources

**Files:**
- Create: `scripts/ingest_ara_corpora.py`
- Create: `data/corpora/greek_nt.csv` (output artifact, committed)
- Create: `data/corpora/peshitta_nt.csv` (output artifact, committed)
- Create: `tests/test_ingest_ara_corpora.py`

**Context:** ARA stores Greek NT as a dict in `data/translations/translations_el.json` (`{"Matthew 1:1": "Βίβλος…", …}`) and Peshitta NT as a CSV in `data/corpora/peshitta_nt.csv` (already in our target format). We transform both into our standard `book_order, book, chapter, verse, reference, text` CSV.

- [ ] **Step 1: Write failing test**

Create `tests/test_ingest_ara_corpora.py`:

```python
"""Test the ARA-to-CSV ingestion of Greek NT and Peshitta NT."""
import csv
import json
from pathlib import Path

from scripts.ingest_ara_corpora import (
    parse_reference,
    convert_greek_translations_to_rows,
    BOOK_ORDER,
)


def test_parse_reference_handles_single_word_books():
    assert parse_reference("Mark 1:1") == ("Mark", 1, 1)
    assert parse_reference("John 3:16") == ("John", 3, 16)


def test_parse_reference_handles_multi_word_books():
    assert parse_reference("1 Corinthians 13:4") == ("1 Corinthians", 13, 4)
    assert parse_reference("Song of Solomon 2:1") == ("Song of Solomon", 2, 1)


def test_book_order_contains_all_27_nt_books():
    assert len(BOOK_ORDER) == 27
    assert BOOK_ORDER["Matthew"] == 40
    assert BOOK_ORDER["Mark"] == 41
    assert BOOK_ORDER["Revelation"] == 66


def test_convert_greek_translations_yields_expected_row_for_mark_1_1():
    raw = {"Mark 1:1": "Ἀρχὴ τοῦ εὐαγγελίου Ἰησοῦ Χριστοῦ."}
    rows = list(convert_greek_translations_to_rows(raw))
    assert rows == [
        {
            "book_order": 41,
            "book": "Mark",
            "chapter": 1,
            "verse": 1,
            "reference": "Mark 1:1",
            "text": "Ἀρχὴ τοῦ εὐαγγελίου Ἰησοῦ Χριστοῦ.",
        }
    ]


def test_convert_greek_translations_skips_malformed_keys(caplog):
    raw = {"Mark 1:1": "ok", "NotARef": "bad", "Mark 1": "missing verse"}
    rows = list(convert_greek_translations_to_rows(raw))
    assert len(rows) == 1
    assert rows[0]["reference"] == "Mark 1:1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ingest_ara_corpora.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.ingest_ara_corpora'`.

- [ ] **Step 3: Write `scripts/ingest_ara_corpora.py`**

```python
"""Ingest Greek NT (JSON) and Peshitta NT (CSV) from the Aramaic Root Atlas repo
into our standard corpus CSV format.

Usage:
    python scripts/ingest_ara_corpora.py --ara-path /path/to/aramaic-root-atlas
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Canonical Protestant NT book order (matches ARA's convention)
BOOK_ORDER: dict[str, int] = {
    "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44,
    "Romans": 45, "1 Corinthians": 46, "2 Corinthians": 47,
    "Galatians": 48, "Ephesians": 49, "Philippians": 50, "Colossians": 51,
    "1 Thessalonians": 52, "2 Thessalonians": 53,
    "1 Timothy": 54, "2 Timothy": 55, "Titus": 56, "Philemon": 57,
    "Hebrews": 58, "James": 59,
    "1 Peter": 60, "2 Peter": 61,
    "1 John": 62, "2 John": 63, "3 John": 64,
    "Jude": 65, "Revelation": 66,
}

REFERENCE_RE = re.compile(r"^(?P<book>.+?)\s+(?P<ch>\d+):(?P<v>\d+)$")


def parse_reference(ref: str) -> tuple[str, int, int]:
    """Parse 'Mark 1:1' or '1 Corinthians 13:4' into (book, chapter, verse)."""
    m = REFERENCE_RE.match(ref.strip())
    if not m:
        raise ValueError(f"Unparseable reference: {ref!r}")
    return m.group("book"), int(m.group("ch")), int(m.group("v"))


def convert_greek_translations_to_rows(raw: dict[str, str]) -> Iterator[dict]:
    """Convert {'Mark 1:1': 'text', ...} into CSV rows. Skips NT-only books;
    malformed keys are logged and skipped."""
    for ref, text in raw.items():
        try:
            book, ch, v = parse_reference(ref)
        except ValueError:
            logger.warning("Skipping malformed reference: %r", ref)
            continue
        if book not in BOOK_ORDER:
            continue  # OT book or unknown
        yield {
            "book_order": BOOK_ORDER[book],
            "book": book,
            "chapter": ch,
            "verse": v,
            "reference": ref,
            "text": text,
        }


def write_csv(rows: list[dict], out_path: Path) -> None:
    fieldnames = ["book_order", "book", "chapter", "verse", "reference", "text"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["book_order"], r["chapter"], r["verse"])):
            w.writerow(row)
    logger.info("Wrote %d rows to %s", len(rows), out_path)


def ingest_greek(ara_path: Path, out_dir: Path) -> None:
    src = ara_path / "data" / "translations" / "translations_el.json"
    if not src.exists():
        raise FileNotFoundError(f"Greek NT source not found at {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    rows = list(convert_greek_translations_to_rows(raw))
    write_csv(rows, out_dir / "greek_nt.csv")


def ingest_peshitta(ara_path: Path, out_dir: Path) -> None:
    src = ara_path / "data" / "corpora" / "peshitta_nt.csv"
    if not src.exists():
        raise FileNotFoundError(f"Peshitta NT source not found at {src}")
    out = out_dir / "peshitta_nt.csv"
    shutil.copy(src, out)
    logger.info("Copied %s -> %s", src, out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ara-path", required=True, type=Path,
                    help="Path to the aramaic-root-atlas repo root")
    ap.add_argument("--out-dir", type=Path, default=Path("data/corpora"))
    args = ap.parse_args()

    ingest_greek(args.ara_path, args.out_dir)
    ingest_peshitta(args.ara_path, args.out_dir)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_ingest_ara_corpora.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the script against the real ARA repo**

```bash
python scripts/ingest_ara_corpora.py --ara-path "/Users/jfresco16/Google Drive/Claude/aramaic-root-atlas"
```
Expected: two files created, `data/corpora/greek_nt.csv` and `data/corpora/peshitta_nt.csv`. Verify:

```bash
wc -l data/corpora/greek_nt.csv data/corpora/peshitta_nt.csv
head -2 data/corpora/greek_nt.csv
```
Expected: ~7940 lines greek_nt, ~7441 lines peshitta_nt (including header). First non-header line starts with `40,Matthew,1,1,"Matthew 1:1",...`.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_ara_corpora.py tests/test_ingest_ara_corpora.py data/corpora/greek_nt.csv data/corpora/peshitta_nt.csv
git commit -m "feat: ingest Greek NT + Peshitta NT corpora from ARA"
```

---

### Task 4: Minimal Flask app with landing page

**Files:**
- Create: `app.py`
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `static/style.css`
- Create: `data/i18n.json`
- Create: `tests/test_routes.py`

**Context:** We build a minimal Flask app that serves `/` and `/about` with copied-and-trimmed ARA styling. Later tasks expand it with viewer routes. We adapt ARA's `base.html` but strip features (bookmarks, QR share) that aren't MVP scope.

- [ ] **Step 1: Write failing test**

Create `tests/test_routes.py`:

```python
"""End-to-end route tests using the Flask test client."""
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Translation Alignment" in resp.data


def test_index_has_cta_to_mark_1_1(client):
    resp = client.get("/")
    assert b"/mark/1/1" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_routes.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Copy ARA's i18n baseline (trimmed)**

```bash
cp "/Users/jfresco16/Google Drive/Claude/aramaic-root-atlas/data/i18n.json" data/i18n.json
```

(We'll trim it to only keys we use in a later task; for now, copying whole is harmless.)

- [ ] **Step 4: Write `app.py`**

```python
"""Translation Alignment Viewer — Flask app.

Thin route layer. Business logic lives in translation_core/.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

# --- Globals (lazy init, ARA pattern) ---
_i18n: dict = {}
_initialized = False
_init_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _init() -> None:
    global _i18n, _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        i18n_path = DATA_DIR / "i18n.json"
        if i18n_path.exists():
            _i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
        _initialized = True


def _t(key: str, lang: str = "en") -> str:
    """Tiny i18n lookup; falls back to the key itself."""
    return _i18n.get(lang, {}).get(key, key)


@app.before_request
def _ensure_init() -> None:
    _init()


@app.context_processor
def _inject_helpers() -> dict:
    return {"t": _t}


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
```

- [ ] **Step 5: Write `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Translation Alignment{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <script src="https://unpkg.com/htmx.org@2.0.2"></script>
</head>
<body>
  <nav class="topbar">
    <a class="brand" href="{{ url_for('index') }}">Translation Alignment</a>
    <div class="nav-right">
      <a href="/about">About</a>
    </div>
  </nav>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
  <footer class="footer">
    <small>Parallel biblical text viewer — MVP · <a href="/about">Methodology</a></small>
  </footer>
</body>
</html>
```

- [ ] **Step 6: Write `templates/index.html`**

```html
{% extends "base.html" %}
{% block title %}Translation Alignment — Home{% endblock %}
{% block content %}
  <section class="hero">
    <h1>Parallel Biblical Text Alignment</h1>
    <p class="lead">
      A focus-verse viewer comparing the Gospel of Mark across three traditions:
      the Greek NT (SBLGNT), the Syriac Peshitta, and the Latin Clementine Vulgate.
      Word-level alignment is pre-computed and highlighted with Chen-style variant coloring.
    </p>
    <a class="cta" href="/mark/1/1">Start reading Mark 1:1 →</a>
  </section>
{% endblock %}
```

- [ ] **Step 7: Write `static/style.css` (baseline, expanded in later tasks)**

```css
:root {
  --bg: #0f0f11;
  --surface: #1a1a1d;
  --border: #2a2a30;
  --text: #e8e8ec;
  --muted: #a0a0a8;
  --accent: #7dd3fc;
  --minor: #4ade80;
  --major: #f87171;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
  font-family: system-ui, -apple-system, sans-serif; }

.topbar { display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; border-bottom: 1px solid var(--border); }
.brand { color: var(--text); text-decoration: none; font-weight: 600; }
.nav-right a { color: var(--muted); text-decoration: none; margin-left: 16px; }
.nav-right a:hover { color: var(--text); }

.container { max-width: 960px; margin: 0 auto; padding: 32px 20px; }

.hero h1 { margin-top: 0; font-size: 2em; }
.hero .lead { color: var(--muted); line-height: 1.6; }
.cta { display: inline-block; margin-top: 16px; padding: 10px 18px;
  background: var(--accent); color: #000; border-radius: 6px;
  text-decoration: none; font-weight: 600; }

.footer { text-align: center; padding: 20px; color: var(--muted);
  border-top: 1px solid var(--border); }
.footer a { color: var(--muted); }
```

- [ ] **Step 8: Run test to verify it passes**

```bash
pytest tests/test_routes.py -v
```
Expected: 2 passed.

- [ ] **Step 9: Manual smoke test**

```bash
python app.py
# Visit http://localhost:5000 in a browser
# Ctrl-C to stop
```
Expected: landing page loads, "Start reading Mark 1:1 →" CTA visible (link will 404 until Task 10).

- [ ] **Step 10: Commit**

```bash
git add app.py templates static data/i18n.json tests/test_routes.py
git commit -m "feat: minimal Flask app with landing page"
```

---

### Task 5: `translation_core.corpora` — CSV loading and reference lookup

**Files:**
- Create: `translation_core/corpora.py`
- Create: `tests/test_corpora.py`

**Context:** Single responsibility: load tradition CSVs into memory and provide O(1) lookup by `(tradition_id, chapter, verse)`. No business logic beyond indexing.

- [ ] **Step 1: Write failing tests**

Create `tests/test_corpora.py`:

```python
"""Test CSV loading and reference-based lookup."""
import pytest
from pathlib import Path

from translation_core.corpora import Corpus, CorpusRegistry


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "book_order,book,chapter,verse,reference,text\n"
        "41,Mark,1,1,Mark 1:1,Archē tou euangeliou\n"
        "41,Mark,1,2,Mark 1:2,Kathōs gegraptai\n"
        "41,Mark,16,20,Mark 16:20,Ekeinoi de exelthontes\n",
        encoding="utf-8",
    )
    return csv_path


def test_corpus_loads_csv_and_looks_up_verse(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    assert c.get("Mark", 1, 1) == "Archē tou euangeliou"
    assert c.get("Mark", 16, 20) == "Ekeinoi de exelthontes"


def test_corpus_returns_none_for_missing_verse(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    assert c.get("Mark", 99, 99) is None
    assert c.get("John", 1, 1) is None


def test_corpus_verse_range_returns_chapter_verses(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    verses = c.verses_in_chapter("Mark", 1)
    assert verses == [1, 2]


def test_registry_loads_multiple_corpora(sample_csv, tmp_path):
    other = tmp_path / "other.csv"
    other.write_text(
        "book_order,book,chapter,verse,reference,text\n"
        "41,Mark,1,1,Mark 1:1,Initium evangelii\n",
        encoding="utf-8",
    )
    reg = CorpusRegistry()
    reg.add("greek_nt", "Greek NT", sample_csv)
    reg.add("vulgate", "Vulgate", other)
    assert reg.get("greek_nt").get("Mark", 1, 1) == "Archē tou euangeliou"
    assert reg.get("vulgate").get("Mark", 1, 1) == "Initium evangelii"
    assert reg.tradition_ids() == ["greek_nt", "vulgate"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_corpora.py -v
```
Expected: FAIL with `ImportError: cannot import name 'Corpus'`.

- [ ] **Step 3: Write `translation_core/corpora.py`**

```python
"""Corpus loading and verse lookup.

A `Corpus` wraps a single tradition's CSV; a `CorpusRegistry` holds multiple
corpora keyed by tradition_id.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Corpus:
    tradition_id: str
    label: str
    csv_path: Path
    _index: dict[tuple[str, int, int], str] = field(default_factory=dict, init=False, repr=False)
    _chapters: dict[tuple[str, int], list[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        with Path(self.csv_path).open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                book = row["book"]
                ch = int(row["chapter"])
                v = int(row["verse"])
                self._index[(book, ch, v)] = row["text"]
                self._chapters.setdefault((book, ch), []).append(v)
        for key in self._chapters:
            self._chapters[key].sort()

    def get(self, book: str, chapter: int, verse: int) -> str | None:
        """Return verse text or None if not present."""
        return self._index.get((book, chapter, verse))

    def verses_in_chapter(self, book: str, chapter: int) -> list[int]:
        """Return sorted list of verse numbers present in the given chapter."""
        return list(self._chapters.get((book, chapter), []))

    def has_verse(self, book: str, chapter: int, verse: int) -> bool:
        return (book, chapter, verse) in self._index


class CorpusRegistry:
    """Holds multiple corpora; preserves insertion order."""

    def __init__(self) -> None:
        self._corpora: dict[str, Corpus] = {}

    def add(self, tradition_id: str, label: str, csv_path: Path) -> None:
        self._corpora[tradition_id] = Corpus(tradition_id, label, csv_path)

    def get(self, tradition_id: str) -> Corpus:
        return self._corpora[tradition_id]

    def tradition_ids(self) -> list[str]:
        return list(self._corpora.keys())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_corpora.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add translation_core/corpora.py tests/test_corpora.py
git commit -m "feat: Corpus + CorpusRegistry with CSV loading and verse lookup"
```

---

### Task 6: Ingest Clementine Vulgate for Mark

**Files:**
- Create: `scripts/ingest_vulgate.py`
- Create: `data/corpora/vulgate.csv` (output artifact)
- Create: `tests/test_ingest_vulgate.py`
- Create: `tests/fixtures/vulgate_mark_sample.txt`

**Context:** We ingest the Clementine Vulgate NT from a public-domain source. The specific source to use: [`github.com/sleepingdog/Clementine-Vulgate`](https://github.com/sleepingdog/Clementine-Vulgate) or the similar `BibleGet-I-O` mirror (**verify URL at run time — if the first isn't available, fall back to any public-domain plain-text Clementine NT**). The ingestion script accepts either a local copy or a URL.

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/vulgate_mark_sample.txt` with a tiny hand-crafted fragment in the format we'll parse. We'll define the parser to expect: one verse per line, prefixed by reference in the form `Mark 1:1\tInitium evangelii...`.

```
Mark 1:1	Initium Evangelii Jesu Christi, Filii Dei.
Mark 1:2	Sicut scriptum est in Isaia propheta : Ecce ego mitto angelum meum ante faciem tuam, qui praeparabit viam tuam ante te.
Mark 1:3	Vox clamantis in deserto : Parate viam Domini, rectas facite semitas ejus.
```

- [ ] **Step 2: Write failing test**

Create `tests/test_ingest_vulgate.py`:

```python
"""Test Vulgate ingestion."""
from pathlib import Path

import pytest

from scripts.ingest_vulgate import parse_vulgate_file, filter_to_book


def test_parse_vulgate_file_reads_tsv_format(tmp_path):
    src = Path("tests/fixtures/vulgate_mark_sample.txt")
    rows = list(parse_vulgate_file(src))
    assert len(rows) == 3
    assert rows[0]["book"] == "Mark"
    assert rows[0]["chapter"] == 1
    assert rows[0]["verse"] == 1
    assert rows[0]["text"].startswith("Initium Evangelii")
    assert rows[0]["book_order"] == 41


def test_filter_to_book_returns_only_target_book():
    rows = [
        {"book": "Mark", "chapter": 1, "verse": 1, "text": "a", "book_order": 41,
         "reference": "Mark 1:1"},
        {"book": "John", "chapter": 1, "verse": 1, "text": "b", "book_order": 43,
         "reference": "John 1:1"},
    ]
    filtered = list(filter_to_book(rows, "Mark"))
    assert len(filtered) == 1
    assert filtered[0]["book"] == "Mark"


def test_parse_vulgate_file_skips_malformed_lines(tmp_path):
    src = tmp_path / "bad.txt"
    src.write_text("Mark 1:1\tgood text\nNOT A LINE\n\nMark 1:2\tanother good\n", encoding="utf-8")
    rows = list(parse_vulgate_file(src))
    assert len(rows) == 2
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_ingest_vulgate.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.ingest_vulgate'`.

- [ ] **Step 4: Write `scripts/ingest_vulgate.py`**

```python
"""Ingest the Clementine Vulgate (Mark only for MVP) into our standard CSV format.

Input format expected: TSV with one verse per line, 'Mark 1:1\\tInitium...'.

The source file must be downloaded manually from a public-domain Clementine Vulgate
corpus (e.g., a mirror of Vulsearch, or github.com/sleepingdog/Clementine-Vulgate).
Place it at the path given via --source.

Usage:
    python scripts/ingest_vulgate.py --source /path/to/vulgate_nt.tsv --book Mark
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Iterator

from scripts.ingest_ara_corpora import BOOK_ORDER, REFERENCE_RE

logger = logging.getLogger(__name__)

LINE_RE = re.compile(r"^(?P<ref>.+?\s+\d+:\d+)\t(?P<text>.+)$")


def parse_vulgate_file(path: Path) -> Iterator[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            m = LINE_RE.match(line)
            if not m:
                logger.debug("Skipping malformed line %d: %r", lineno, line[:80])
                continue
            ref = m.group("ref")
            ref_match = REFERENCE_RE.match(ref)
            if not ref_match:
                logger.debug("Skipping line with unparseable ref at %d: %r", lineno, ref)
                continue
            book = ref_match.group("book")
            if book not in BOOK_ORDER:
                continue
            yield {
                "book_order": BOOK_ORDER[book],
                "book": book,
                "chapter": int(ref_match.group("ch")),
                "verse": int(ref_match.group("v")),
                "reference": ref,
                "text": m.group("text"),
            }


def filter_to_book(rows: Iterator[dict], book: str) -> Iterator[dict]:
    for row in rows:
        if row["book"] == book:
            yield row


def write_csv(rows: list[dict], out_path: Path) -> None:
    fieldnames = ["book_order", "book", "chapter", "verse", "reference", "text"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["book_order"], r["chapter"], r["verse"]))
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    logger.info("Wrote %d rows to %s", len(rows), out_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to the Clementine Vulgate TSV source file")
    ap.add_argument("--book", default=None,
                    help="Optional: filter to a single book (e.g., 'Mark')")
    ap.add_argument("--out", type=Path, default=Path("data/corpora/vulgate.csv"))
    args = ap.parse_args()

    rows = list(parse_vulgate_file(args.source))
    if args.book:
        rows = list(filter_to_book(rows, args.book))
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_ingest_vulgate.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Source the Clementine Vulgate and run the script**

Download a public-domain Clementine Vulgate. Recommended: clone `github.com/sleepingdog/Clementine-Vulgate` (or the first available public-domain mirror you can verify). Convert its format to the TSV our parser expects. If the source is in a different format (USFM, plain chapter files, etc.), write a one-shot preprocessor — document in a `scripts/README.md` note — and produce `vulgate_nt.tsv`.

Run:
```bash
python scripts/ingest_vulgate.py --source /path/to/vulgate_nt.tsv --book Mark
```

Verify:
```bash
wc -l data/corpora/vulgate.csv           # ~679 lines (header + 678 verses)
head -2 data/corpora/vulgate.csv
```

Expected: `41,Mark,1,1,"Mark 1:1","Initium Evangelii..."`. Visually scan the last 2-3 verses of Mark 16 to confirm completeness.

**If the Vulgate has a versification mismatch for Mark** (e.g., Mark 16:9–20 in the long ending), note in `known-issues.md` (create a stub if not yet existing); alignments for mismatched verses will be handled at generation time with `absent`.

- [ ] **Step 7: Commit**

```bash
git add scripts/ingest_vulgate.py tests/test_ingest_vulgate.py tests/fixtures/vulgate_mark_sample.txt data/corpora/vulgate.csv
git commit -m "feat: ingest Clementine Vulgate (Mark) into corpus CSV"
```

---

## Phase 3 — Alignment schema, fixtures, and viewer skeleton (Tasks 7–11)

### Task 7: Alignment JSON schema + validator + fixture

**Files:**
- Create: `translation_core/schema.py`
- Create: `tests/test_schema.py`
- Create: `data/alignments/_fixtures/alignment_mark_1_1.json`

- [ ] **Step 1: Write failing test**

Create `tests/test_schema.py`:

```python
"""Test alignment JSON schema validation."""
import json
from pathlib import Path

import pytest

from translation_core.schema import validate_alignment, AlignmentValidationError


@pytest.fixture
def valid_alignment() -> dict:
    return {
        "ref": "Mark 1:1",
        "chapter": 1,
        "verse": 1,
        "traditions": {
            "greek_nt": {"tokens": ["Ἀρχὴ", "τοῦ", "εὐαγγελίου"]},
            "peshitta": {"tokens": ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ"]},
            "vulgate":  {"tokens": ["Initium", "evangelii"]},
        },
        "alignment": [
            {"greek_nt": [0], "peshitta": [0], "vulgate": [0], "variant": "aligned"},
            {"greek_nt": [1, 2], "peshitta": [1], "vulgate": [1], "variant": "minor"},
        ],
        "meta": {
            "generated_by": "claude-sonnet-4-6",
            "generated_at": "2026-04-22T10:00:00Z",
            "confidence": 0.87,
            "schema_version": 1,
        },
    }


def test_valid_alignment_passes(valid_alignment):
    validate_alignment(valid_alignment)  # should not raise


def test_missing_ref_fails(valid_alignment):
    del valid_alignment["ref"]
    with pytest.raises(AlignmentValidationError, match="ref"):
        validate_alignment(valid_alignment)


def test_invalid_variant_fails(valid_alignment):
    valid_alignment["alignment"][0]["variant"] = "weird"
    with pytest.raises(AlignmentValidationError, match="variant"):
        validate_alignment(valid_alignment)


def test_token_index_out_of_bounds_fails(valid_alignment):
    valid_alignment["alignment"][0]["greek_nt"] = [99]
    with pytest.raises(AlignmentValidationError, match="out of bounds"):
        validate_alignment(valid_alignment)


def test_absent_tradition_is_allowed(valid_alignment):
    valid_alignment["traditions"]["vulgate"] = {"absent": True}
    # Remove vulgate from every alignment group to satisfy consistency
    for group in valid_alignment["alignment"]:
        group.pop("vulgate", None)
    validate_alignment(valid_alignment)


def test_confidence_out_of_range_fails(valid_alignment):
    valid_alignment["meta"]["confidence"] = 1.5
    with pytest.raises(AlignmentValidationError, match="confidence"):
        validate_alignment(valid_alignment)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_schema.py -v
```
Expected: FAIL with `ImportError: cannot import name 'validate_alignment'`.

- [ ] **Step 3: Write `translation_core/schema.py`**

```python
"""Alignment JSON schema and validator.

Instead of pulling in jsonschema for such a small schema, we do hand-coded
validation — errors are more specific and testable.
"""
from __future__ import annotations

VALID_VARIANTS = {"aligned", "minor", "major", "omitted", "added"}
REQUIRED_TOP_FIELDS = {"ref", "chapter", "verse", "traditions", "alignment", "meta"}
REQUIRED_META_FIELDS = {"generated_by", "generated_at", "confidence", "schema_version"}


class AlignmentValidationError(ValueError):
    """Raised when an alignment JSON fails validation."""


def validate_alignment(data: dict) -> None:
    """Raise AlignmentValidationError if the alignment is invalid."""

    missing = REQUIRED_TOP_FIELDS - data.keys()
    if missing:
        raise AlignmentValidationError(
            f"Missing required top-level fields: {sorted(missing)} (expected 'ref' etc.)"
        )

    traditions = data["traditions"]
    if not isinstance(traditions, dict) or not traditions:
        raise AlignmentValidationError("'traditions' must be a non-empty object")

    # Token lengths by tradition for bounds checking
    token_lens: dict[str, int | None] = {}
    for trad_id, trad in traditions.items():
        if not isinstance(trad, dict):
            raise AlignmentValidationError(f"Tradition {trad_id!r} must be an object")
        if trad.get("absent") is True:
            token_lens[trad_id] = None
            continue
        tokens = trad.get("tokens")
        if not isinstance(tokens, list):
            raise AlignmentValidationError(
                f"Tradition {trad_id!r} missing 'tokens' list (or mark as 'absent': true)"
            )
        token_lens[trad_id] = len(tokens)

    alignment = data["alignment"]
    if not isinstance(alignment, list):
        raise AlignmentValidationError("'alignment' must be a list")

    for i, group in enumerate(alignment):
        variant = group.get("variant")
        if variant not in VALID_VARIANTS:
            raise AlignmentValidationError(
                f"alignment[{i}]: invalid variant {variant!r}; "
                f"must be one of {sorted(VALID_VARIANTS)}"
            )
        for trad_id, indices in group.items():
            if trad_id == "variant" or trad_id == "note":
                continue
            if trad_id not in traditions:
                raise AlignmentValidationError(
                    f"alignment[{i}]: unknown tradition {trad_id!r}"
                )
            if not isinstance(indices, list) or not all(isinstance(x, int) for x in indices):
                raise AlignmentValidationError(
                    f"alignment[{i}].{trad_id}: must be a list of integers"
                )
            tok_len = token_lens.get(trad_id)
            if tok_len is None:
                raise AlignmentValidationError(
                    f"alignment[{i}]: tradition {trad_id!r} is marked absent; "
                    f"remove it from this group"
                )
            for idx in indices:
                if idx < 0 or idx >= tok_len:
                    raise AlignmentValidationError(
                        f"alignment[{i}].{trad_id}: index {idx} out of bounds "
                        f"(tradition has {tok_len} tokens)"
                    )

    meta = data["meta"]
    missing_meta = REQUIRED_META_FIELDS - meta.keys()
    if missing_meta:
        raise AlignmentValidationError(
            f"meta missing fields: {sorted(missing_meta)}"
        )
    conf = meta["confidence"]
    if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
        raise AlignmentValidationError(
            f"meta.confidence must be a number in [0, 1], got {conf!r}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_schema.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Write the Mark 1:1 fixture**

Create `data/alignments/_fixtures/alignment_mark_1_1.json`:

```json
{
  "ref": "Mark 1:1",
  "chapter": 1,
  "verse": 1,
  "traditions": {
    "greek_nt": {
      "tokens": ["Ἀρχὴ", "τοῦ", "εὐαγγελίου", "Ἰησοῦ", "Χριστοῦ", "υἱοῦ", "θεοῦ"]
    },
    "peshitta": {
      "tokens": ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ", "ܕܝܫܘܥ", "ܡܫܝܚܐ", "ܒܪܗ", "ܕܐܠܗܐ"]
    },
    "vulgate": {
      "tokens": ["Initium", "evangelii", "Iesu", "Christi", "Filii", "Dei"]
    }
  },
  "alignment": [
    {"greek_nt": [0], "peshitta": [0], "vulgate": [0], "variant": "aligned"},
    {"greek_nt": [1, 2], "peshitta": [1], "vulgate": [1], "variant": "aligned"},
    {"greek_nt": [3, 4], "peshitta": [2, 3], "vulgate": [2, 3], "variant": "aligned"},
    {"greek_nt": [5, 6], "peshitta": [4, 5], "vulgate": [4, 5], "variant": "minor",
     "note": "Vulgate uses post-classical genitive construction Filii Dei"}
  ],
  "meta": {
    "generated_by": "hand-crafted-fixture",
    "generated_at": "2026-04-22T12:00:00Z",
    "confidence": 1.0,
    "schema_version": 1
  }
}
```

- [ ] **Step 6: Verify fixture passes validation**

```bash
python -c "import json; from translation_core.schema import validate_alignment; validate_alignment(json.load(open('data/alignments/_fixtures/alignment_mark_1_1.json')))"
```
Expected: no output (success).

- [ ] **Step 7: Commit**

```bash
git add translation_core/schema.py tests/test_schema.py data/alignments/_fixtures/alignment_mark_1_1.json
git commit -m "feat: alignment JSON schema, validator, and Mark 1:1 fixture"
```

---

### Task 8: `translation_core.alignment` — load and look up alignment JSON

**Files:**
- Create: `translation_core/alignment.py`
- Create: `tests/test_alignment.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_alignment.py`:

```python
"""Test alignment loading and lookup."""
import json
import shutil
from pathlib import Path

import pytest

from translation_core.alignment import AlignmentStore


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    # Copy fixture into a tmp alignments/mark/1/1.json layout
    fixture = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dest = tmp_path / "mark" / "1"
    dest.mkdir(parents=True)
    shutil.copy(fixture, dest / "1.json")
    return tmp_path


def test_load_existing_verse(store_dir):
    store = AlignmentStore(root=store_dir)
    data = store.get("Mark", 1, 1)
    assert data is not None
    assert data["ref"] == "Mark 1:1"
    assert len(data["alignment"]) == 4


def test_load_missing_verse_returns_none(store_dir):
    store = AlignmentStore(root=store_dir)
    assert store.get("Mark", 99, 99) is None


def test_validates_on_load(store_dir):
    # Corrupt the fixture
    bad = store_dir / "mark" / "1" / "2.json"
    bad.write_text(json.dumps({"ref": "Mark 1:2"}), encoding="utf-8")
    store = AlignmentStore(root=store_dir)
    with pytest.raises(Exception):  # AlignmentValidationError
        store.get("Mark", 1, 2)


def test_caches_after_first_load(store_dir):
    store = AlignmentStore(root=store_dir)
    first = store.get("Mark", 1, 1)
    second = store.get("Mark", 1, 1)
    assert first is second  # same dict object (cached)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_alignment.py -v
```
Expected: FAIL on import.

- [ ] **Step 3: Write `translation_core/alignment.py`**

```python
"""Load and look up per-verse alignment JSON from the data/alignments tree."""
from __future__ import annotations

import json
from pathlib import Path

from translation_core.schema import validate_alignment


class AlignmentStore:
    """Serves alignment JSON from `<root>/<book_lower>/<chapter>/<verse>.json`.

    Validates each JSON on first load and caches the parsed dict in memory.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._cache: dict[tuple[str, int, int], dict] = {}

    def _path_for(self, book: str, chapter: int, verse: int) -> Path:
        return self.root / book.lower() / str(chapter) / f"{verse}.json"

    def get(self, book: str, chapter: int, verse: int) -> dict | None:
        key = (book, chapter, verse)
        if key in self._cache:
            return self._cache[key]
        path = self._path_for(book, chapter, verse)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_alignment(data)  # raises on invalid
        self._cache[key] = data
        return data

    def has(self, book: str, chapter: int, verse: int) -> bool:
        return self._path_for(book, chapter, verse).exists()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_alignment.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add translation_core/alignment.py tests/test_alignment.py
git commit -m "feat: AlignmentStore with lazy load, schema validation, caching"
```

---

### Task 9: `translation_core.rendering` — alignment → HTML verse card

**Files:**
- Create: `translation_core/rendering.py`
- Create: `tests/test_rendering.py`

**Context:** One Jinja macro, invoked from `_verse.html` (Task 10). For each tradition's tokens, wrap each token in a span whose class depends on the variant group it participates in. Build a `token_idx -> variant` map from the alignment groups.

- [ ] **Step 1: Write failing tests**

Create `tests/test_rendering.py`:

```python
"""Test alignment → HTML rendering."""
import json
from pathlib import Path

import pytest

from translation_core.rendering import token_variant_map, render_tokens_html


@pytest.fixture
def fixture_data() -> dict:
    p = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    return json.loads(p.read_text(encoding="utf-8"))


def test_token_variant_map_assigns_minor_to_right_tokens(fixture_data):
    m = token_variant_map(fixture_data, "greek_nt")
    # Group 4 is 'minor', covers greek indices 5, 6
    assert m[5] == "minor"
    assert m[6] == "minor"
    assert m[0] == "aligned"


def test_render_tokens_html_wraps_with_variant_classes(fixture_data):
    html = render_tokens_html(fixture_data, "greek_nt")
    assert '<span class="tok aligned"' in html
    assert '<span class="tok minor"' in html
    # Each token should appear exactly once (in its span text)
    assert html.count(">Ἀρχὴ<") == 1
    assert html.count(">θεοῦ<") == 1


def test_render_tokens_html_adds_aria_label_for_non_aligned(fixture_data):
    html = render_tokens_html(fixture_data, "greek_nt")
    # Aligned tokens get no aria-label; minor/major tokens do
    assert 'aria-label="θεοῦ — minor variant"' in html or 'aria-label="υἱοῦ — minor variant"' in html


def test_render_tokens_html_handles_absent_tradition():
    data = {
        "ref": "Mark 99:99",
        "chapter": 99, "verse": 99,
        "traditions": {"vulgate": {"absent": True}},
        "alignment": [],
        "meta": {"generated_by": "test", "generated_at": "2026-04-22",
                 "confidence": 1.0, "schema_version": 1},
    }
    html = render_tokens_html(data, "vulgate")
    assert "absent" in html.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rendering.py -v
```
Expected: FAIL on import.

- [ ] **Step 3: Write `translation_core/rendering.py`**

```python
"""Render alignment JSON into HTML fragments for the viewer.

Kept pure-Python (no Jinja) so it can be unit-tested without a Flask app context.
The route layer invokes these helpers and passes the resulting HTML as safe markup
to Jinja.
"""
from __future__ import annotations

from html import escape


def token_variant_map(alignment: dict, tradition_id: str) -> dict[int, str]:
    """Map token index → variant for the given tradition.

    Tokens not covered by any group default to 'aligned'.
    """
    trad = alignment["traditions"].get(tradition_id, {})
    if trad.get("absent"):
        return {}
    n = len(trad.get("tokens", []))
    result: dict[int, str] = {i: "aligned" for i in range(n)}
    for group in alignment["alignment"]:
        variant = group.get("variant", "aligned")
        for idx in group.get(tradition_id, []):
            result[idx] = variant
    return result


def render_tokens_html(alignment: dict, tradition_id: str) -> str:
    """Render a tradition's tokens as `<span class="tok {variant}">token</span>`.

    Returns a complete HTML fragment (tokens separated by spaces).
    If the tradition is marked absent, returns a placeholder fragment.
    """
    trad = alignment["traditions"].get(tradition_id, {})
    if trad.get("absent"):
        return '<p class="tok-absent"><em>absent in this tradition</em></p>'

    tokens = trad.get("tokens", [])
    variants = token_variant_map(alignment, tradition_id)
    variant_labels = {
        "aligned": "",
        "minor": "minor variant",
        "major": "major variant",
        "omitted": "omitted",
        "added": "added",
    }
    parts: list[str] = []
    for i, tok in enumerate(tokens):
        variant = variants.get(i, "aligned")
        label = variant_labels.get(variant, "")
        aria = f' aria-label="{escape(tok)} — {label}"' if label else ""
        parts.append(
            f'<span class="tok {variant}" data-idx="{i}" '
            f'data-tradition="{tradition_id}"{aria}>{escape(tok)}</span>'
        )
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_rendering.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add translation_core/rendering.py tests/test_rendering.py
git commit -m "feat: render alignment tokens to HTML with variant classes"
```

---

### Task 10: Viewer routes `/mark/<ch>/<v>` + htmx partial + templates

**Files:**
- Modify: `app.py`
- Create: `templates/viewer.html`
- Create: `templates/_verse.html`
- Modify: `static/style.css`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Extend `tests/test_routes.py` with viewer tests**

Append to `tests/test_routes.py`:

```python
def test_viewer_route_renders_fixture_verse(client):
    # Copy fixture into data/alignments/mark/1/1.json for the test
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        resp = client.get("/mark/1/1")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Ἀρχὴ" in body
        assert "ܪܫܐ" in body
        assert "Initium" in body
        assert 'class="tok' in body
    finally:
        dst.unlink()


def test_viewer_partial_returns_card_only(client):
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        resp = client.get("/partials/verse/mark/1/1")
        body = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Ἀρχὴ" in body
        # Partial should NOT include the full HTML skeleton
        assert "<!DOCTYPE" not in body
        assert "<nav" not in body
    finally:
        dst.unlink()


def test_viewer_returns_404_for_nonexistent_verse(client):
    resp = client.get("/mark/1/999")
    assert resp.status_code == 404


def test_viewer_redirects_bad_chapter_verse_format(client):
    resp = client.get("/mark/abc/xyz")
    # Flask's converter will return 404 for non-int routes; acceptable
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py -v
```
Expected: 4 new failures (route not defined yet).

- [ ] **Step 3: Expand `app.py` with corpora, alignment store, viewer routes**

Replace `app.py` with:

```python
"""Translation Alignment Viewer — Flask app."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from flask import Flask, abort, render_template, url_for
from markupsafe import Markup

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

# Tradition display metadata (id, label, script direction)
TRADITIONS = [
    ("greek_nt", "Greek NT", "ltr"),
    ("peshitta", "Peshitta",  "rtl"),
    ("vulgate",  "Vulgate",   "ltr"),
]

# Map our runtime tradition IDs to the corpus CSVs. Note: we use 'peshitta' as
# the short ID for display, but the CSV file is peshitta_nt.csv.
CORPUS_FILES = {
    "greek_nt": "greek_nt.csv",
    "peshitta": "peshitta_nt.csv",
    "vulgate":  "vulgate.csv",
}


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/mark/<int:chapter>/<int:verse>")
def viewer(chapter: int, verse: int):
    alignment = _alignments.get("Mark", chapter, verse)
    if alignment is None:
        # Fall back to text-only if we have the corpus rows but no alignment
        fallback = _build_fallback(chapter, verse)
        if fallback is None:
            abort(404)
        return render_template(
            "viewer.html", alignment=fallback, alignment_pending=True,
            chapter=chapter, verse=verse,
            render_tokens_html=render_tokens_html,
        )
    return render_template(
        "viewer.html", alignment=alignment, alignment_pending=False,
        chapter=chapter, verse=verse,
        render_tokens_html=render_tokens_html,
    )


@app.route("/partials/verse/mark/<int:chapter>/<int:verse>")
def viewer_partial(chapter: int, verse: int):
    alignment = _alignments.get("Mark", chapter, verse)
    if alignment is None:
        fallback = _build_fallback(chapter, verse)
        if fallback is None:
            abort(404)
        return render_template(
            "_verse.html", alignment=fallback, alignment_pending=True,
            chapter=chapter, verse=verse,
            render_tokens_html=render_tokens_html,
        )
    return render_template(
        "_verse.html", alignment=alignment, alignment_pending=False,
        chapter=chapter, verse=verse,
        render_tokens_html=render_tokens_html,
    )


def _build_fallback(chapter: int, verse: int) -> dict | None:
    """If alignment JSON doesn't exist but the corpus has the verse, return a
    minimal 'alignment'-shaped dict with raw text as a single-token tradition,
    and an empty alignment list. Returns None if no tradition has the verse.
    """
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
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
```

- [ ] **Step 4: Write `templates/viewer.html`**

```html
{% extends "base.html" %}
{% block title %}Mark {{ chapter }}:{{ verse }} — Translation Alignment{% endblock %}
{% block content %}
  <div id="verse-container" hx-target="this" hx-swap="outerHTML">
    {% include "_verse.html" %}
  </div>
{% endblock %}
```

- [ ] **Step 5: Write `templates/_verse.html`**

```html
<article class="verse-card" data-chapter="{{ chapter }}" data-verse="{{ verse }}">
  <header class="verse-header">
    <h2>Mark {{ chapter }}:{{ verse }}</h2>
    {% if alignment_pending %}
      <span class="badge alignment-pending">alignment pending</span>
    {% endif %}
    <nav class="verse-nav">
      {% set prev_v = verse - 1 %}
      {% set next_v = verse + 1 %}
      <a class="nav-prev" href="/mark/{{ chapter }}/{{ prev_v }}"
         hx-get="/partials/verse/mark/{{ chapter }}/{{ prev_v }}"
         hx-push-url="/mark/{{ chapter }}/{{ prev_v }}"
         hx-target="#verse-container" hx-swap="innerHTML">← prev</a>
      <a class="nav-next" href="/mark/{{ chapter }}/{{ next_v }}"
         hx-get="/partials/verse/mark/{{ chapter }}/{{ next_v }}"
         hx-push-url="/mark/{{ chapter }}/{{ next_v }}"
         hx-target="#verse-container" hx-swap="innerHTML">next →</a>
    </nav>
  </header>

  <div class="verse-columns">
    {% for tid, label, dir in traditions %}
      <section class="trad-col" data-tradition="{{ tid }}" dir="{{ dir }}">
        <span class="trad-label">{{ label }}</span>
        <div class="trad-text {{ tid }}">
          {{ render_tokens_html(alignment, tid) | safe }}
        </div>
      </section>
    {% endfor %}
  </div>

  {% set notes = alignment.alignment | selectattr("note") | list %}
  {% if notes %}
    <div class="commentary">
      <h3>Variant notes</h3>
      <ul>
        {% for group in notes %}
          <li><span class="variant-dot {{ group.variant }}"></span>{{ group.note }}</li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}
</article>
```

- [ ] **Step 6: Expand `static/style.css` with verse-card styles**

Append to `static/style.css`:

```css
/* Verse card */
.verse-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 20px; margin: 20px 0; }
.verse-header { display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
.verse-header h2 { margin: 0; font-size: 1.4em; }
.verse-nav a { color: var(--accent); text-decoration: none; margin-left: 12px; }
.verse-nav a:hover { text-decoration: underline; }

.verse-columns { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
@media (max-width: 800px) { .verse-columns { grid-template-columns: 1fr; } }

.trad-col { padding: 12px; border-right: 1px solid var(--border); }
.trad-col:last-child { border-right: none; }
@media (max-width: 800px) { .trad-col { border-right: none;
  border-bottom: 1px solid var(--border); } }

.trad-label { display: block; font-size: 10px; text-transform: uppercase;
  letter-spacing: 1.5px; color: var(--muted); margin-bottom: 8px; }
.trad-text { line-height: 1.7; font-size: 1.05em; }
.trad-text.greek_nt { font-family: 'GFS Didot', 'Cardo', 'Times New Roman', serif; }
.trad-text.peshitta { font-family: 'Estrangelo Edessa', 'Serto Jerusalem', serif;
  font-size: 1.2em; }
.trad-text.vulgate { font-family: 'Cardo', 'Times New Roman', serif; font-style: italic; }

/* Variant coloring */
.tok { padding: 1px 0; }
.tok.aligned {}
.tok.minor { text-decoration: underline wavy var(--minor);
  text-decoration-thickness: 1.5px; text-underline-offset: 3px; }
.tok.major { text-decoration: underline wavy var(--major);
  text-decoration-thickness: 1.5px; text-underline-offset: 3px; }
.tok.omitted, .tok.added { text-decoration: underline dotted var(--muted); }

.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
  background: var(--border); color: var(--muted); font-size: 11px; }

.commentary { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border);
  font-size: 0.9em; }
.commentary h3 { font-size: 12px; text-transform: uppercase;
  letter-spacing: 1.5px; color: var(--muted); margin: 0 0 8px; }
.variant-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 8px; vertical-align: middle; }
.variant-dot.minor { background: var(--minor); }
.variant-dot.major { background: var(--major); }

.tok-absent { color: var(--muted); font-style: italic; }
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```
Expected: all 6 tests pass.

- [ ] **Step 8: Manual smoke test**

Copy the fixture into `data/alignments/mark/1/1.json` (NOT a commit — one-off manual test):
```bash
mkdir -p data/alignments/mark/1
cp data/alignments/_fixtures/alignment_mark_1_1.json data/alignments/mark/1/1.json
python app.py
# Visit http://localhost:5000/mark/1/1 — verify 3-column render with Chen-style underlines
# Then delete the temp file:
rm data/alignments/mark/1/1.json
```

- [ ] **Step 9: Commit**

```bash
git add app.py templates/viewer.html templates/_verse.html static/style.css tests/test_routes.py
git commit -m "feat: viewer routes, htmx partial, and verse-card template"
```

---

### Task 11: Prev/next navigation respects chapter boundaries

**Files:**
- Modify: `app.py`
- Modify: `templates/_verse.html`
- Modify: `tests/test_routes.py`

**Context:** The current prev/next links naively compute `verse - 1` / `verse + 1`, which breaks at chapter boundaries (`Mark 1:0`, `Mark 1:999`). We fix this by looking up the actual valid neighbor via `CorpusRegistry`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_routes.py`:

```python
def test_nav_wraps_to_next_chapter_at_chapter_end(client):
    # Assumes greek_nt.csv has Mark 1 with at least some verses
    # and Mark 2:1 exists. We check the generated nav links.
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        # Request Mark 1:1 — prev should be disabled, next should be /mark/1/2
        resp = client.get("/mark/1/1")
        body = resp.data.decode("utf-8")
        assert "/mark/1/2" in body
        # prev link absent or disabled (no /mark/1/0 or /mark/0/*)
        assert "/mark/1/0" not in body
        assert "/mark/0/" not in body
    finally:
        dst.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_routes.py::test_nav_wraps_to_next_chapter_at_chapter_end -v
```
Expected: FAIL — current template emits `/mark/1/0`.

- [ ] **Step 3: Add neighbor-lookup helper to `app.py`**

Add after the TRADITIONS constant:

```python
def _neighbor(chapter: int, verse: int, direction: int) -> tuple[int, int] | None:
    """Return (chapter, verse) of the neighbor in the given direction (+1 or -1).

    Uses the Greek NT corpus as the master reference for which verses exist
    (since we're sure this corpus is complete for Mark).
    """
    try:
        master = _corpora.get("greek_nt")
    except KeyError:
        return None
    if direction == +1:
        # Try next verse in same chapter
        if master.has_verse("Mark", chapter, verse + 1):
            return (chapter, verse + 1)
        # Else try verse 1 of next chapter
        if master.has_verse("Mark", chapter + 1, 1):
            return (chapter + 1, 1)
        return None
    else:
        if verse > 1 and master.has_verse("Mark", chapter, verse - 1):
            return (chapter, verse - 1)
        # Else jump to last verse of previous chapter
        if chapter > 1:
            verses = master.verses_in_chapter("Mark", chapter - 1)
            if verses:
                return (chapter - 1, verses[-1])
        return None
```

Then update both `viewer` and `viewer_partial` to pass `prev` and `next` to the template:

```python
# Inside viewer() and viewer_partial(), after the `alignment = ...` lookup:
prev_v = _neighbor(chapter, verse, -1)
next_v = _neighbor(chapter, verse, +1)
return render_template(
    "viewer.html",  # or "_verse.html"
    alignment=alignment, alignment_pending=<same_as_before>,
    chapter=chapter, verse=verse,
    prev=prev_v, next=next_v,
    render_tokens_html=render_tokens_html,
)
```

- [ ] **Step 4: Update `templates/_verse.html` to use prev/next**

Replace the `<nav class="verse-nav">` block with:

```html
<nav class="verse-nav">
  {% if prev %}
    <a class="nav-prev" href="/mark/{{ prev[0] }}/{{ prev[1] }}"
       hx-get="/partials/verse/mark/{{ prev[0] }}/{{ prev[1] }}"
       hx-push-url="/mark/{{ prev[0] }}/{{ prev[1] }}"
       hx-target="#verse-container" hx-swap="innerHTML">← {{ prev[0] }}:{{ prev[1] }}</a>
  {% else %}
    <span class="nav-prev disabled">← start</span>
  {% endif %}
  {% if next %}
    <a class="nav-next" href="/mark/{{ next[0] }}/{{ next[1] }}"
       hx-get="/partials/verse/mark/{{ next[0] }}/{{ next[1] }}"
       hx-push-url="/mark/{{ next[0] }}/{{ next[1] }}"
       hx-target="#verse-container" hx-swap="innerHTML">{{ next[0] }}:{{ next[1] }} →</a>
  {% else %}
    <span class="nav-next disabled">end →</span>
  {% endif %}
</nav>
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app.py templates/_verse.html tests/test_routes.py
git commit -m "feat: chapter-aware prev/next navigation"
```

---

## Phase 4 — Enrichment data (Tasks 12–14)

### Task 12: Extract STEP TAGNT enrichment for Mark

**Files:**
- Create: `scripts/extract_step_enrichment.py`
- Create: `data/enrichment/greek_strong.json`
- Create: `tests/test_extract_step_enrichment.py`
- Create: `tests/fixtures/tagnt_sample.txt`

**Context:** Clone `github.com/STEPBible/STEPBible-Data` (or download a release tarball), locate `Translators Amalgamated OT+NT/TAGNT Mat-Jhn - …CC-BY.txt` (exact filename may drift — verify at run time). Parse its TSV columns, filter to Mark, emit a compact JSON keyed by `"Mark 1:1"` with a list of per-token entries.

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/tagnt_sample.txt` with a minimal slice of the TAGNT format. The real TAGNT is TSV with a complex header; for the fixture, we construct a simplified version that matches our parser's expectations:

```
#Ref	Greek	EnglishGloss	dStrongMorph	LemmaGloss	Editions
Mrk.1.1#01	Ἀρχὴ	[The] beginning	G0746=N-NSF	ἀρχή=beginning	NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz
Mrk.1.1#02	τοῦ	[of] the	G3588T=T-GSN	ὁ=the	NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz
Mrk.1.1#03	εὐαγγελίου	gospel	G2098=N-GSN	εὐαγγέλιον=gospel	NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz
Mrk.1.2#01	Καθὼς	Just as	G2531=ADV	καθώς=just as	NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_extract_step_enrichment.py`:

```python
"""Test STEP TAGNT parsing."""
from pathlib import Path

import pytest

from scripts.extract_step_enrichment import parse_tagnt_line, parse_tagnt_file, filter_to_book


def test_parse_tagnt_line_extracts_token_and_strong():
    line = ("Mrk.1.1#01\tἈρχὴ\t[The] beginning\tG0746=N-NSF\tἀρχή=beginning\t"
            "NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz")
    result = parse_tagnt_line(line)
    assert result["book"] == "Mark"
    assert result["chapter"] == 1
    assert result["verse"] == 1
    assert result["token_idx"] == 0  # #01 -> zero-based
    assert result["token"] == "Ἀρχὴ"
    assert result["strong"] == "G0746"
    assert result["morph"] == "N-NSF"
    assert result["lemma"] == "ἀρχή"
    assert result["gloss"] == "[The] beginning"


def test_parse_tagnt_file_returns_dict_keyed_by_ref():
    src = Path("tests/fixtures/tagnt_sample.txt")
    result = parse_tagnt_file(src)
    assert "Mark 1:1" in result
    assert len(result["Mark 1:1"]) == 3
    assert result["Mark 1:1"][0]["token"] == "Ἀρχὴ"
    assert "Mark 1:2" in result


def test_filter_to_book_limits_to_single_book():
    data = {"Mark 1:1": [], "John 1:1": [], "Mark 2:1": []}
    out = filter_to_book(data, "Mark")
    assert set(out.keys()) == {"Mark 1:1", "Mark 2:1"}


def test_parse_tagnt_line_returns_none_on_comment_or_blank():
    assert parse_tagnt_line("#Ref\tGreek\t...") is None
    assert parse_tagnt_line("") is None
    assert parse_tagnt_line("\n") is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_extract_step_enrichment.py -v
```
Expected: FAIL on import.

- [ ] **Step 4: Write `scripts/extract_step_enrichment.py`**

```python
"""Extract per-token enrichment (Strong's, morph, lemma, gloss) for Mark from
STEP Bible's tagged NT (TAGNT) file.

Usage:
    python scripts/extract_step_enrichment.py \\
        --source /path/to/STEPBible-Data/Translators\\ Amalgamated\\ OT+NT/<TAGNT file> \\
        --book Mark
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Lookup to convert STEP's 3-letter book codes to our book names
STEP_BOOK_MAP: dict[str, str] = {
    "Mat": "Matthew", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
    "Act": "Acts",
    "Rom": "Romans", "1Co": "1 Corinthians", "2Co": "2 Corinthians",
    "Gal": "Galatians", "Eph": "Ephesians", "Php": "Philippians", "Col": "Colossians",
    "1Th": "1 Thessalonians", "2Th": "2 Thessalonians",
    "1Ti": "1 Timothy", "2Ti": "2 Timothy", "Tit": "Titus", "Phm": "Philemon",
    "Heb": "Hebrews", "Jas": "James",
    "1Pe": "1 Peter", "2Pe": "2 Peter",
    "1Jn": "1 John", "2Jn": "2 John", "3Jn": "3 John",
    "Jud": "Jude", "Rev": "Revelation",
}

# Match 'Mrk.1.1#01' prefix
REF_RE = re.compile(r"^(?P<book>[A-Za-z0-9]+)\.(?P<ch>\d+)\.(?P<v>\d+)#(?P<tok>\d+)")


def parse_tagnt_line(line: str) -> dict | None:
    """Parse a single TAGNT TSV row into a dict, or return None if not a data row."""
    if not line or line.startswith("#") or line.strip() == "":
        return None
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 5:
        return None
    ref_m = REF_RE.match(parts[0])
    if not ref_m:
        return None
    book_code = ref_m.group("book")
    book = STEP_BOOK_MAP.get(book_code)
    if not book:
        return None
    # dStrong+morph column: e.g. 'G0746=N-NSF'
    strong_morph = parts[3] if len(parts) > 3 else ""
    strong, _, morph = strong_morph.partition("=")
    # lemma+gloss column: e.g. 'ἀρχή=beginning'
    lemma_gloss = parts[4] if len(parts) > 4 else ""
    lemma, _, _lemma_gloss = lemma_gloss.partition("=")
    return {
        "book": book,
        "chapter": int(ref_m.group("ch")),
        "verse": int(ref_m.group("v")),
        "token_idx": int(ref_m.group("tok")) - 1,  # zero-based
        "token": parts[1],
        "gloss": parts[2] if len(parts) > 2 else "",
        "strong": strong,
        "morph": morph,
        "lemma": lemma,
    }


def parse_tagnt_file(path: Path) -> dict[str, list[dict]]:
    """Return {'Mark 1:1': [token_entries], ...}."""
    result: dict[str, list[dict]] = {}
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            entry = parse_tagnt_line(line)
            if not entry:
                continue
            ref = f"{entry['book']} {entry['chapter']}:{entry['verse']}"
            result.setdefault(ref, []).append({
                "token_idx": entry["token_idx"],
                "token": entry["token"],
                "strong": entry["strong"],
                "morph": entry["morph"],
                "lemma": entry["lemma"],
                "gloss": entry["gloss"],
            })
    # Sort each verse's entries by token_idx
    for entries in result.values():
        entries.sort(key=lambda e: e["token_idx"])
    return result


def filter_to_book(data: dict[str, list[dict]], book: str) -> dict[str, list[dict]]:
    prefix = f"{book} "
    return {k: v for k, v in data.items() if k.startswith(prefix)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to STEP TAGNT ... CC-BY.txt file")
    ap.add_argument("--book", default="Mark")
    ap.add_argument("--out", type=Path, default=Path("data/enrichment/greek_strong.json"))
    args = ap.parse_args()

    data = parse_tagnt_file(args.source)
    filtered = filter_to_book(data, args.book)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote enrichment for %d verses to %s", len(filtered), args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_extract_step_enrichment.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Source the STEP data and run**

```bash
# Clone STEP data into a sibling directory (adjust path as needed)
git clone --depth 1 https://github.com/STEPBible/STEPBible-Data.git /tmp/STEPBible-Data
# Locate the TAGNT file (filename may include date/version):
ls "/tmp/STEPBible-Data/Translators Amalgamated OT+NT/" | grep -i "TAGNT Mat-Jhn"
# Run:
python scripts/extract_step_enrichment.py \
  --source "/tmp/STEPBible-Data/Translators Amalgamated OT+NT/TAGNT Mat-Jhn - <actual-filename>.txt" \
  --book Mark
```

Verify:
```bash
python -c "import json; d = json.load(open('data/enrichment/greek_strong.json')); print(len(d), 'verses;', 'Mark 1:1 tokens:', len(d['Mark 1:1']))"
```
Expected: ~678 verses, Mark 1:1 tokens ≥ 6.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_step_enrichment.py tests/test_extract_step_enrichment.py tests/fixtures/tagnt_sample.txt data/enrichment/greek_strong.json
git commit -m "feat: extract Greek Strong's/morph/lemma enrichment from STEP TAGNT"
```

---

### Task 13: `translation_core.enrichment` + tooltip endpoints

**Files:**
- Create: `translation_core/enrichment.py`
- Create: `tests/test_enrichment.py`
- Create: `templates/_tooltip_greek.html`
- Create: `templates/_tooltip_peshitta.html`
- Modify: `app.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichment.py`:

```python
"""Test enrichment data lookup."""
import json
from pathlib import Path

import pytest

from translation_core.enrichment import GreekEnrichment, PeshittaEnrichment


@pytest.fixture
def greek_data(tmp_path: Path) -> Path:
    p = tmp_path / "greek.json"
    p.write_text(json.dumps({
        "Mark 1:1": [
            {"token_idx": 0, "token": "Ἀρχὴ", "strong": "G0746",
             "morph": "N-NSF", "lemma": "ἀρχή", "gloss": "[The] beginning"},
            {"token_idx": 1, "token": "τοῦ", "strong": "G3588",
             "morph": "T-GSN", "lemma": "ὁ", "gloss": "[of] the"},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_greek_lookup_returns_entry(greek_data):
    ge = GreekEnrichment(path=greek_data)
    entry = ge.lookup("Mark", 1, 1, 0)
    assert entry is not None
    assert entry["strong"] == "G0746"
    assert entry["lemma"] == "ἀρχή"


def test_greek_lookup_returns_none_for_missing(greek_data):
    ge = GreekEnrichment(path=greek_data)
    assert ge.lookup("Mark", 1, 1, 99) is None
    assert ge.lookup("Mark", 99, 99, 0) is None


def test_peshitta_lookup_returns_entry(tmp_path):
    p = tmp_path / "peshitta.json"
    p.write_text(json.dumps({
        "Mark 1:1": [
            {"token_idx": 0, "token": "ܪܫܐ", "root": "R-SH-A",
             "sister_roots": ["R-SH-M"], "cognates": {"hebrew": "ראש", "arabic": "رأس"}},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    pe = PeshittaEnrichment(path=p)
    entry = pe.lookup("Mark", 1, 1, 0)
    assert entry is not None
    assert entry["root"] == "R-SH-A"
    assert "R-SH-M" in entry["sister_roots"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_enrichment.py -v
```
Expected: FAIL on import.

- [ ] **Step 3: Write `translation_core/enrichment.py`**

```python
"""Per-token enrichment lookup for Greek (STEP) and Peshitta (ARA) tokens."""
from __future__ import annotations

import json
from pathlib import Path


class _EnrichmentBase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def lookup(self, book: str, chapter: int, verse: int, token_idx: int) -> dict | None:
        ref = f"{book} {chapter}:{verse}"
        entries = self._data.get(ref)
        if not entries:
            return None
        for entry in entries:
            if entry.get("token_idx") == token_idx:
                return entry
        return None


class GreekEnrichment(_EnrichmentBase):
    """Strong's number, lemma, morph, English gloss per Greek token."""


class PeshittaEnrichment(_EnrichmentBase):
    """Root, sister roots, Hebrew/Arabic cognates per Peshitta token."""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_enrichment.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Add tooltip routes to `app.py`**

Add after the viewer routes:

```python
from translation_core.enrichment import GreekEnrichment, PeshittaEnrichment

# Add to globals:
_greek_enrichment: GreekEnrichment | None = None
_peshitta_enrichment: PeshittaEnrichment | None = None

# Inside _init(), after _alignments = ...:
global _greek_enrichment, _peshitta_enrichment
_greek_enrichment = GreekEnrichment(DATA_DIR / "enrichment" / "greek_strong.json")
_peshitta_enrichment = PeshittaEnrichment(DATA_DIR / "enrichment" / "peshitta_roots.json")


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
```

- [ ] **Step 6: Write tooltip templates**

Create `templates/_tooltip_greek.html`:

```html
<div class="tooltip-inner greek-tooltip">
  <div class="tt-token">{{ entry.token }}</div>
  <dl class="tt-fields">
    <dt>Strong's</dt><dd>{{ entry.strong }}</dd>
    <dt>Lemma</dt><dd>{{ entry.lemma }}</dd>
    <dt>Morph</dt><dd>{{ entry.morph }}</dd>
    <dt>Gloss</dt><dd>{{ entry.gloss }}</dd>
  </dl>
</div>
```

Create `templates/_tooltip_peshitta.html`:

```html
<div class="tooltip-inner peshitta-tooltip">
  <div class="tt-token" dir="rtl">{{ entry.token }}</div>
  <dl class="tt-fields">
    <dt>Root</dt><dd>{{ entry.root or '—' }}</dd>
    {% if entry.sister_roots %}
      <dt>Sister roots</dt><dd>{{ entry.sister_roots | join(', ') }}</dd>
    {% endif %}
    {% if entry.cognates %}
      <dt>Hebrew</dt><dd>{{ entry.cognates.get('hebrew', '—') }}</dd>
      <dt>Arabic</dt><dd>{{ entry.cognates.get('arabic', '—') }}</dd>
    {% endif %}
  </dl>
</div>
```

- [ ] **Step 7: Write route test**

Append to `tests/test_routes.py`:

```python
def test_tooltip_greek_returns_entry_when_present(client):
    # This test requires data/enrichment/greek_strong.json to exist with Mark 1:1
    resp = client.get("/tooltip/greek/1/1/0")
    if resp.status_code == 404:
        pytest.skip("greek_strong.json not yet populated")
    assert resp.status_code == 200
    assert b"G0746" in resp.data or b"Strong" in resp.data


def test_tooltip_greek_404_for_missing_token(client):
    resp = client.get("/tooltip/greek/99/99/0")
    assert resp.status_code == 404
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_routes.py tests/test_enrichment.py -v
```
Expected: all pass (greek tooltip test may skip if enrichment JSON absent — acceptable for CI until Task 12 data lands).

- [ ] **Step 9: Commit**

```bash
git add translation_core/enrichment.py tests/test_enrichment.py templates/_tooltip_greek.html templates/_tooltip_peshitta.html app.py tests/test_routes.py
git commit -m "feat: Greek/Peshitta enrichment lookup + tooltip routes"
```

---

### Task 14: Snapshot Peshitta root data from ARA

**Files:**
- Create: `scripts/snapshot_ara_roots.py`
- Create: `data/enrichment/peshitta_roots.json`
- Create: `tests/test_snapshot_ara_roots.py`

**Context:** Import ARA's `aramaic_core` package, walk every Peshitta word in Mark, extract root, sister roots, and cognate info. Because ARA is installed in a sibling directory (not a pip package), we add its path to `sys.path` at script start time.

- [ ] **Step 1: Write failing test**

Create `tests/test_snapshot_ara_roots.py`:

```python
"""Test the ARA-root snapshot script's pure helpers."""
import pytest

from scripts.snapshot_ara_roots import tokenize_verse, build_verse_entry


def test_tokenize_verse_splits_on_whitespace():
    assert tokenize_verse("ܪܫܐ ܕܐܘܢܓܠܝܘܢ ܕܝܫܘܥ") == ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ", "ܕܝܫܘܥ"]


def test_build_verse_entry_returns_empty_list_for_empty_verse():
    entries = build_verse_entry("", lambda tok: None)
    assert entries == []


def test_build_verse_entry_calls_root_fn_per_token():
    calls = []
    def fake_root(tok: str):
        calls.append(tok)
        return {"root": f"ROOT({tok})", "sister_roots": [], "cognates": {}}
    entries = build_verse_entry("a b c", fake_root)
    assert calls == ["a", "b", "c"]
    assert entries[0]["token_idx"] == 0
    assert entries[0]["root"] == "ROOT(a)"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_snapshot_ara_roots.py -v
```
Expected: FAIL on import.

- [ ] **Step 3: Write `scripts/snapshot_ara_roots.py`**

```python
"""Snapshot per-Peshitta-token root data from the Aramaic Root Atlas package
into a flat JSON file usable by our viewer.

Requires a local clone of `aramaic-root-atlas` with its Python package importable.

Usage:
    python scripts/snapshot_ara_roots.py \\
        --ara-path /path/to/aramaic-root-atlas \\
        --book Mark
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def tokenize_verse(text: str) -> list[str]:
    """Simple whitespace tokenizer. Matches what the alignment generator uses."""
    return text.split()


def build_verse_entry(text: str, root_fn: Callable[[str], dict | None]) -> list[dict]:
    """For each token in text, call root_fn(token) and build an enrichment entry.

    root_fn returns a dict with keys {root, sister_roots, cognates} or None.
    """
    entries: list[dict] = []
    for i, tok in enumerate(tokenize_verse(text)):
        info = root_fn(tok)
        if info is None:
            info = {"root": None, "sister_roots": [], "cognates": {}}
        entries.append({
            "token_idx": i,
            "token": tok,
            "root": info.get("root"),
            "sister_roots": info.get("sister_roots", []),
            "cognates": info.get("cognates", {}),
        })
    return entries


def _load_ara_root_fn(ara_path: Path) -> Callable[[str], dict | None]:
    """Import ARA and return a function that takes a Syriac word and returns root info.

    The exact ARA API may drift; adjust the imports below to match the current
    aramaic_core package layout. As of the MVP design date, the relevant
    entry points are RootExtractor.extract() and CognateLookup.cognates_for_root().
    """
    sys.path.insert(0, str(ara_path))
    from aramaic_core.extractor import RootExtractor
    from aramaic_core.cognates import CognateLookup
    from aramaic_core.characters import transliterate_syriac

    extractor = RootExtractor()
    cog = CognateLookup()
    # ARA uses a 'roots/cognates.json' file for cognate data; load it if available
    cognates_path = ara_path / "data" / "roots" / "cognates.json"
    if cognates_path.exists():
        cog.load_from_file(cognates_path)

    def root_fn(token: str) -> dict | None:
        try:
            root = extractor.extract(token)
        except Exception:
            return None
        if not root:
            return None
        sister = extractor.sister_roots(root) if hasattr(extractor, "sister_roots") else []
        hebrew = cog.to_hebrew(root) if hasattr(cog, "to_hebrew") else None
        arabic = cog.to_arabic(root) if hasattr(cog, "to_arabic") else None
        return {
            "root": transliterate_syriac(root) if root else None,
            "sister_roots": sister or [],
            "cognates": {"hebrew": hebrew or "", "arabic": arabic or ""},
        }

    return root_fn


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ara-path", required=True, type=Path)
    ap.add_argument("--book", default="Mark")
    ap.add_argument("--csv", type=Path, default=Path("data/corpora/peshitta_nt.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/enrichment/peshitta_roots.json"))
    args = ap.parse_args()

    root_fn = _load_ara_root_fn(args.ara_path)
    output: dict[str, list[dict]] = {}
    with args.csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["book"] != args.book:
                continue
            ref = row["reference"]
            output[ref] = build_verse_entry(row["text"], root_fn)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %d verses of Peshitta root enrichment to %s", len(output), args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_snapshot_ara_roots.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run against real ARA**

```bash
python scripts/snapshot_ara_roots.py \
  --ara-path "/Users/jfresco16/Google Drive/Claude/aramaic-root-atlas" \
  --book Mark
```

**Caveat:** ARA's API surface may not match the imports in `_load_ara_root_fn` exactly. If the import fails or a method is missing, either (a) read the current `aramaic_core/` module to find the equivalent function, or (b) document the gap in `known-issues.md` and emit a placeholder `peshitta_roots.json` where every entry has `root: null, sister_roots: [], cognates: {}`. The viewer tolerates missing enrichment.

- [ ] **Step 6: Commit**

```bash
git add scripts/snapshot_ara_roots.py tests/test_snapshot_ara_roots.py data/enrichment/peshitta_roots.json
git commit -m "feat: snapshot Peshitta root enrichment from Aramaic Root Atlas"
```

---

## Phase 5 — Alignment generation (Tasks 15–17)

### Task 15: 10-verse pilot generation with Claude (calibration)

**Files:**
- Create: `scripts/generate_alignments.py`
- Create: `scripts/prompts/align_3way.md`
- Create: `tests/test_generate_alignments.py`
- Create: `tests/fixtures/few_shot_examples.json`

**Context:** Before running the full book, generate 10 representative verses (Mark 1:1, 1:15, 3:27, 5:41, 8:29, 10:45, 13:14, 14:36, 15:34, 16:8) using the synchronous Claude API. Measure tokens and time. Confirms the prompt works before we commit to a batch run.

- [ ] **Step 1: Write the prompt file**

Create `scripts/prompts/align_3way.md`:

```
You are a rigorous parallel-text alignment engine for biblical scholars. Given the same verse in three traditions (Greek NT, Syriac Peshitta, Latin Vulgate), produce a token-by-token alignment.

INPUT
You will receive:
- `greek_tokens`: whitespace-split Greek NT tokens (SBLGNT)
- `peshitta_tokens`: whitespace-split Peshitta tokens (Syriac script)
- `vulgate_tokens`: whitespace-split Clementine Vulgate tokens
- `enrichment.greek_strong`: per-Greek-token {strong, lemma, morph, gloss}
- `enrichment.peshitta_roots`: per-Peshitta-token {root, sister_roots, cognates}

OUTPUT
Return JSON matching this schema exactly:

{
  "alignment": [
    { "greek_nt": [i, ...], "peshitta": [j, ...], "vulgate": [k, ...],
      "variant": "aligned" | "minor" | "major" | "omitted" | "added",
      "note": "<optional short scholarly comment>" }
  ],
  "confidence": <float in [0, 1]>
}

VARIANT DEFINITIONS
- `aligned`: same meaning, same lemma family, no notable difference
- `minor`: synonymous or stylistic (word order, particle choice, synonym)
- `major`: semantic change, substantive addition or substitution
- `omitted`: a phrase in one or more traditions has no counterpart in another
- `added`: inverse of `omitted`

RULES
1. Every token index from every tradition must appear in at least one group. No duplicates.
2. Use `aligned` when the Greek lemma + Peshitta root + Vulgate lemma all map to the same semantic unit.
3. Use `omitted`/`added` when a span exists in one tradition but not another; show the present indices and omit the absent tradition from the group.
4. A `note` is required for `major` and encouraged for `minor`; omit for `aligned`.
5. `confidence` reflects your overall confidence in the alignment: 1.0 = trivial; 0.8 = routine; 0.5 = real uncertainty; <0.5 = flag for review.

Return only the JSON. No prose.
```

- [ ] **Step 2: Write the few-shot examples file**

Create `tests/fixtures/few_shot_examples.json`:

```json
{
  "Mark 1:1": {
    "input": {
      "greek_tokens": ["Ἀρχὴ", "τοῦ", "εὐαγγελίου", "Ἰησοῦ", "Χριστοῦ", "υἱοῦ", "θεοῦ"],
      "peshitta_tokens": ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ", "ܕܝܫܘܥ", "ܡܫܝܚܐ", "ܒܪܗ", "ܕܐܠܗܐ"],
      "vulgate_tokens": ["Initium", "evangelii", "Iesu", "Christi", "Filii", "Dei"]
    },
    "output": {
      "alignment": [
        {"greek_nt": [0], "peshitta": [0], "vulgate": [0], "variant": "aligned"},
        {"greek_nt": [1, 2], "peshitta": [1], "vulgate": [1], "variant": "aligned"},
        {"greek_nt": [3, 4], "peshitta": [2, 3], "vulgate": [2, 3], "variant": "aligned"},
        {"greek_nt": [5, 6], "peshitta": [4, 5], "vulgate": [4, 5], "variant": "minor",
         "note": "Vulgate Filii Dei uses post-classical Latin genitive construction"}
      ],
      "confidence": 0.95
    }
  }
}
```

- [ ] **Step 3: Write failing tests for the pure helpers**

Create `tests/test_generate_alignments.py`:

```python
"""Test the generate_alignments script's pure helpers."""
import json
from pathlib import Path

import pytest

from scripts.generate_alignments import (
    build_user_message,
    validate_and_normalize_response,
    PILOT_VERSES,
)


def test_pilot_contains_10_verses():
    assert len(PILOT_VERSES) == 10
    assert ("Mark", 1, 1) in PILOT_VERSES


def test_build_user_message_includes_all_three_traditions():
    msg = build_user_message(
        greek_tokens=["a", "b"],
        peshitta_tokens=["x"],
        vulgate_tokens=["y"],
        enrichment={"greek_strong": [], "peshitta_roots": []},
    )
    assert '"greek_tokens"' in msg
    assert '"peshitta_tokens"' in msg
    assert '"vulgate_tokens"' in msg


def test_validate_and_normalize_accepts_valid_response():
    raw = {
        "alignment": [
            {"greek_nt": [0, 1], "peshitta": [0], "vulgate": [0], "variant": "aligned"}
        ],
        "confidence": 0.9,
    }
    traditions = {
        "greek_nt": {"tokens": ["a", "b"]},
        "peshitta": {"tokens": ["x"]},
        "vulgate":  {"tokens": ["y"]},
    }
    result = validate_and_normalize_response(raw, traditions, ref="Mark 1:1",
                                             chapter=1, verse=1,
                                             model="claude-sonnet-4-6")
    assert result["ref"] == "Mark 1:1"
    assert result["meta"]["confidence"] == 0.9
    assert result["meta"]["generated_by"] == "claude-sonnet-4-6"


def test_validate_and_normalize_rejects_missing_alignment_key():
    with pytest.raises(Exception):
        validate_and_normalize_response({"confidence": 0.9}, traditions={}, ref="x",
                                        chapter=1, verse=1, model="x")
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/test_generate_alignments.py -v
```
Expected: FAIL on import.

- [ ] **Step 5: Write `scripts/generate_alignments.py`**

```python
"""Generate 3-way alignments for Mark via Claude.

Modes:
    --pilot             Generate the 10-verse calibration sample (sync API)
    --full              Generate all remaining verses (Batch API recommended)
    --verse Mark 1:1    Generate a single specific verse (sync API)

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from translation_core.schema import validate_alignment, AlignmentValidationError
from translation_core.corpora import CorpusRegistry

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

# 10 pilot verses spanning Mark's stylistic range
PILOT_VERSES: list[tuple[str, int, int]] = [
    ("Mark", 1, 1),   # opening incipit
    ("Mark", 1, 15),  # Jesus' first teaching
    ("Mark", 3, 27),  # strong man parable
    ("Mark", 5, 41),  # Talitha koum (Aramaic retained)
    ("Mark", 8, 29),  # Peter's confession
    ("Mark", 10, 45), # ransom saying
    ("Mark", 13, 14), # abomination
    ("Mark", 14, 36), # Gethsemane
    ("Mark", 15, 34), # cry from the cross
    ("Mark", 16, 8),  # short-ending final verse
]

PROMPT_DIR = Path(__file__).parent / "prompts"
FEW_SHOT_FIXTURE = Path("tests/fixtures/few_shot_examples.json")


def load_system_prompt() -> str:
    return (PROMPT_DIR / "align_3way.md").read_text(encoding="utf-8")


def load_few_shot_examples() -> list[dict]:
    if not FEW_SHOT_FIXTURE.exists():
        return []
    return list(json.loads(FEW_SHOT_FIXTURE.read_text(encoding="utf-8")).values())


def build_user_message(
    greek_tokens: list[str],
    peshitta_tokens: list[str],
    vulgate_tokens: list[str],
    enrichment: dict,
) -> str:
    """Build the per-verse user message as a JSON blob."""
    payload = {
        "greek_tokens": greek_tokens,
        "peshitta_tokens": peshitta_tokens,
        "vulgate_tokens": vulgate_tokens,
        "enrichment": enrichment,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def call_claude_sync(
    client,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
    user_msg: str,
) -> dict:
    """Call Claude's Messages API with prompt caching on the static context."""
    # Build few-shot as paired user/assistant messages
    messages: list[dict] = []
    for ex in few_shot:
        messages.append({"role": "user", "content": json.dumps(ex["input"], ensure_ascii=False)})
        messages.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)})
    messages.append({"role": "user", "content": user_msg})

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.1,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    text = response.content[0].text
    # Defensive: strip code fences if the model wraps them
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json\n"):
            text = text[5:]
    return json.loads(text)


def validate_and_normalize_response(
    raw: dict,
    traditions: dict,
    ref: str,
    chapter: int,
    verse: int,
    model: str,
) -> dict:
    """Wrap the Claude response in our canonical alignment JSON shape and validate."""
    if "alignment" not in raw:
        raise ValueError(f"Response missing 'alignment' key: {raw!r}")
    confidence = raw.get("confidence", 0.5)
    data = {
        "ref": ref,
        "chapter": chapter,
        "verse": verse,
        "traditions": traditions,
        "alignment": raw["alignment"],
        "meta": {
            "generated_by": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "confidence": float(confidence),
            "schema_version": 1,
        },
    }
    validate_alignment(data)
    return data


def generate_one_verse(
    client,
    corpora: CorpusRegistry,
    greek_enrich: dict,
    peshitta_enrich: dict,
    book: str,
    chapter: int,
    verse: int,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
) -> dict:
    """Produce a single alignment dict for a verse, raising on failure."""
    greek = corpora.get("greek_nt").get(book, chapter, verse) or ""
    peshitta = corpora.get("peshitta").get(book, chapter, verse) or ""
    vulgate = corpora.get("vulgate").get(book, chapter, verse) or ""

    greek_tokens = greek.split()
    peshitta_tokens = peshitta.split()
    vulgate_tokens = vulgate.split()

    ref = f"{book} {chapter}:{verse}"
    enrichment = {
        "greek_strong": greek_enrich.get(ref, []),
        "peshitta_roots": peshitta_enrich.get(ref, []),
    }
    user_msg = build_user_message(greek_tokens, peshitta_tokens, vulgate_tokens, enrichment)

    raw = call_claude_sync(client, model, system_prompt, few_shot, user_msg)

    traditions = {
        "greek_nt": {"tokens": greek_tokens} if greek_tokens else {"absent": True},
        "peshitta": {"tokens": peshitta_tokens} if peshitta_tokens else {"absent": True},
        "vulgate":  {"tokens": vulgate_tokens} if vulgate_tokens else {"absent": True},
    }
    return validate_and_normalize_response(raw, traditions, ref, chapter, verse, model)


def save_alignment(data: dict, out_root: Path) -> Path:
    ch = data["chapter"]
    v = data["verse"]
    out = out_root / "mark" / str(ch) / f"{v}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_pilot(client, corpora, greek_enrich, peshitta_enrich, out_root: Path,
              model: str, system_prompt: str, few_shot: list[dict]) -> dict:
    """Generate PILOT_VERSES, report per-verse token counts and durations."""
    stats = {"verses": [], "total_input_tokens": 0, "total_output_tokens": 0,
             "started_at": time.time()}
    for book, ch, v in PILOT_VERSES:
        t0 = time.time()
        try:
            data = generate_one_verse(client, corpora, greek_enrich, peshitta_enrich,
                                      book, ch, v, model, system_prompt, few_shot)
            save_alignment(data, out_root)
            ok = True
            err = None
        except Exception as e:
            ok = False
            err = str(e)
            data = None
        dur = time.time() - t0
        stats["verses"].append({"ref": f"{book} {ch}:{v}", "ok": ok,
                                "duration_s": round(dur, 2), "error": err})
        logger.info("  %s  %.2fs  %s", f"{book} {ch}:{v}", dur, "ok" if ok else f"FAIL: {err}")
    stats["elapsed_s"] = round(time.time() - stats["started_at"], 2)
    return stats


def _load_all(data_dir: Path):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    corpora = CorpusRegistry()
    corpora.add("greek_nt", "Greek NT", data_dir / "corpora" / "greek_nt.csv")
    corpora.add("peshitta", "Peshitta", data_dir / "corpora" / "peshitta_nt.csv")
    corpora.add("vulgate",  "Vulgate",  data_dir / "corpora" / "vulgate.csv")
    greek_enrich = json.loads((data_dir / "enrichment" / "greek_strong.json").read_text(encoding="utf-8"))
    peshitta_enrich_path = data_dir / "enrichment" / "peshitta_roots.json"
    peshitta_enrich = json.loads(peshitta_enrich_path.read_text(encoding="utf-8")) if peshitta_enrich_path.exists() else {}
    return client, corpora, greek_enrich, peshitta_enrich


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="Run the 10-verse pilot")
    ap.add_argument("--verse", nargs=3, metavar=("BOOK", "CH", "V"),
                    help="Generate a single verse")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()

    client, corpora, greek_enrich, peshitta_enrich = _load_all(args.data_dir)
    system_prompt = load_system_prompt()
    few_shot = load_few_shot_examples()
    out_root = args.data_dir / "alignments"

    if args.pilot:
        stats = run_pilot(client, corpora, greek_enrich, peshitta_enrich,
                          out_root, args.model, system_prompt, few_shot)
        (out_root / "_pilot_stats.json").write_text(
            json.dumps(stats, indent=2), encoding="utf-8"
        )
        logger.info("Pilot complete. Stats saved to %s/_pilot_stats.json", out_root)
    elif args.verse:
        book, ch, v = args.verse[0], int(args.verse[1]), int(args.verse[2])
        data = generate_one_verse(client, corpora, greek_enrich, peshitta_enrich,
                                   book, ch, v, args.model, system_prompt, few_shot)
        path = save_alignment(data, out_root)
        logger.info("Wrote %s", path)
    else:
        ap.error("specify --pilot or --verse")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_generate_alignments.py -v
```
Expected: 4 passed.

- [ ] **Step 7: Run the pilot against the real API**

```bash
python scripts/generate_alignments.py --pilot
```

Inspect `data/alignments/_pilot_stats.json`. Expected: 10 verses, all ok, each <5s, total <60s.

Inspect two or three generated files by hand (`data/alignments/mark/1/1.json`, etc.) — verify alignments look sane (tokens match original text, variants reasonable).

- [ ] **Step 8: Smoke-test the viewer**

```bash
python app.py
# Visit http://localhost:5000/mark/1/1
# Verify the pilot alignment renders with variant underlines
# Navigate next/prev (most won't exist yet — expect "alignment pending" badge)
```

- [ ] **Step 9: Commit**

```bash
git add scripts/generate_alignments.py scripts/prompts/align_3way.md tests/test_generate_alignments.py tests/fixtures/few_shot_examples.json data/alignments/_pilot_stats.json data/alignments/mark/
git commit -m "feat: Claude alignment generation pipeline + 10-verse pilot"
```

---

### Task 16: Full-book generation via Batch API

**Files:**
- Modify: `scripts/generate_alignments.py`

**Context:** With the pilot validated, scale to all ~678 Mark verses using Anthropic's Batch API (50% cost discount, up to 24h turnaround). Each batch can hold up to 100,000 requests; ours is trivially small.

- [ ] **Step 1: Add batch-mode support to `scripts/generate_alignments.py`**

Add imports and new helpers near the top, above `main()`:

```python
def build_batch_requests(
    corpora: CorpusRegistry,
    greek_enrich: dict,
    peshitta_enrich: dict,
    out_root: Path,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
    force: bool = False,
) -> list[dict]:
    """Build one request per Mark verse that doesn't already have a valid JSON."""
    requests = []
    master = corpora.get("greek_nt")
    for ch in range(1, 17):
        for v in master.verses_in_chapter("Mark", ch):
            target = out_root / "mark" / str(ch) / f"{v}.json"
            if target.exists() and not force:
                continue
            greek = master.get("Mark", ch, v) or ""
            peshitta = corpora.get("peshitta").get("Mark", ch, v) or ""
            vulgate = corpora.get("vulgate").get("Mark", ch, v) or ""
            ref = f"Mark {ch}:{v}"
            enrichment = {
                "greek_strong": greek_enrich.get(ref, []),
                "peshitta_roots": peshitta_enrich.get(ref, []),
            }
            user_msg = build_user_message(
                greek.split(), peshitta.split(), vulgate.split(), enrichment
            )
            messages = []
            for ex in few_shot:
                messages.append({"role": "user",
                                 "content": json.dumps(ex["input"], ensure_ascii=False)})
                messages.append({"role": "assistant",
                                 "content": json.dumps(ex["output"], ensure_ascii=False)})
            messages.append({"role": "user", "content": user_msg})
            requests.append({
                "custom_id": f"mark_{ch}_{v}",
                "params": {
                    "model": model,
                    "max_tokens": 2000,
                    "temperature": 0.1,
                    "system": [
                        {"type": "text", "text": system_prompt,
                         "cache_control": {"type": "ephemeral"}}
                    ],
                    "messages": messages,
                },
            })
    return requests


def submit_batch_and_wait(client, requests: list[dict], poll_interval: int = 30) -> dict:
    """Submit batch, poll until done, return {custom_id: response_dict}."""
    from anthropic.types.messages.batch_create_params import Request as BatchReq

    batch = client.messages.batches.create(
        requests=[BatchReq(**r) for r in requests]
    )
    logger.info("Submitted batch %s with %d requests", batch.id, len(requests))

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        counts = batch.request_counts
        logger.info("  batch %s status=%s succeeded=%d errored=%d",
                    batch.id, batch.processing_status, counts.succeeded, counts.errored)
        time.sleep(poll_interval)

    # Stream results
    results: dict[str, dict] = {}
    for result in client.messages.batches.results(batch.id):
        cid = result.custom_id
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json\n"):
                    text = text[5:]
            try:
                results[cid] = json.loads(text)
            except Exception as e:
                logger.error("  %s: JSON parse failed: %s", cid, e)
                results[cid] = {"_error": str(e), "_raw": text[:500]}
        else:
            err = result.result.error if hasattr(result.result, "error") else result.result
            logger.error("  %s: %s", cid, err)
            results[cid] = {"_error": str(err)}
    return results
```

Extend `main()`:

```python
    ap.add_argument("--full", action="store_true",
                    help="Generate all Mark verses via Batch API")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if a verse JSON already exists")
```

After the `--verse` branch, add:

```python
    elif args.full:
        requests = build_batch_requests(corpora, greek_enrich, peshitta_enrich,
                                         out_root, args.model, system_prompt,
                                         few_shot, force=args.force)
        if not requests:
            logger.info("No verses to generate (all exist; use --force to regenerate)")
            return
        logger.info("Submitting batch with %d verse requests", len(requests))
        results = submit_batch_and_wait(client, requests)

        ok = 0
        fail = 0
        quarantine = out_root / "_quarantine"
        for cid, raw in results.items():
            _prefix, ch_str, v_str = cid.split("_")
            ch, v = int(ch_str), int(v_str)
            greek = corpora.get("greek_nt").get("Mark", ch, v) or ""
            peshitta = corpora.get("peshitta").get("Mark", ch, v) or ""
            vulgate = corpora.get("vulgate").get("Mark", ch, v) or ""
            traditions = {
                "greek_nt": {"tokens": greek.split()} if greek else {"absent": True},
                "peshitta": {"tokens": peshitta.split()} if peshitta else {"absent": True},
                "vulgate":  {"tokens": vulgate.split()} if vulgate else {"absent": True},
            }
            if "_error" in raw:
                quarantine.mkdir(parents=True, exist_ok=True)
                (quarantine / f"{cid}.json").write_text(
                    json.dumps(raw, indent=2), encoding="utf-8"
                )
                fail += 1
                continue
            try:
                data = validate_and_normalize_response(
                    raw, traditions, f"Mark {ch}:{v}", ch, v, args.model
                )
                save_alignment(data, out_root)
                ok += 1
            except AlignmentValidationError as e:
                quarantine.mkdir(parents=True, exist_ok=True)
                (quarantine / f"{cid}.json").write_text(
                    json.dumps({"_error": str(e), "raw": raw}, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                fail += 1
        logger.info("Full run done. succeeded=%d quarantined=%d", ok, fail)
```

- [ ] **Step 2: Dry-run the batch (build requests only, don't submit)**

Because submitting a real batch costs money and wall-clock time, verify the request construction first by running with a mock:

```bash
python -c "
from scripts.generate_alignments import build_batch_requests, load_system_prompt, load_few_shot_examples, _load_all
from pathlib import Path
c, corp, ge, pe = _load_all(Path('data'))
reqs = build_batch_requests(corp, ge, pe, Path('data/alignments'),
                             'claude-sonnet-4-6', load_system_prompt(),
                             load_few_shot_examples())
print(f'{len(reqs)} requests built. First custom_id: {reqs[0][\"custom_id\"] if reqs else None}')
print(f'First request messages length: {len(reqs[0][\"params\"][\"messages\"]) if reqs else 0}')
"
```

Expected: ~668 requests built (678 total minus the 10 already done in the pilot; if force=False).

- [ ] **Step 3: Submit the real batch**

```bash
python scripts/generate_alignments.py --full
```

This will log progress every 30s while the batch processes. Expected wall clock: 5–30 minutes for ~668 verses (batches usually finish in minutes unless Anthropic is under heavy load).

- [ ] **Step 4: Verify coverage**

```bash
find data/alignments/mark -name "*.json" | wc -l
```
Expected: ~678 files (should match the verse count from `verses_in_chapter` sum).

Check quarantine:
```bash
ls data/alignments/_quarantine/ 2>/dev/null
```
Expected: ideally empty; if not, inspect each for error cause.

- [ ] **Step 5: Commit data and pipeline changes**

```bash
git add scripts/generate_alignments.py data/alignments/mark/
git commit -m "feat: Batch API full-book alignment generation for Mark"
```

---

### Task 17: Quality loop — low-confidence report + known-issues

**Files:**
- Modify: `scripts/generate_alignments.py`
- Create: `known-issues.md`

**Context:** Sonnet-only pipeline. We don't re-run low-confidence verses with a stronger model — re-running Sonnet on the same prompt would produce nearly the same output. Instead, we emit a report that lists every verse with `confidence < 0.7`, plus anything in `_quarantine/`, so a human can review them.

- [ ] **Step 1: Add a `--report` mode**

Append to `scripts/generate_alignments.py` (inside `main()`):

```python
    ap.add_argument("--report", action="store_true",
                    help="Print low-confidence and quarantined verses for manual review")
    ap.add_argument("--threshold", type=float, default=0.7)
```

And the branch:

```python
    elif args.report:
        low_conf = []
        for ch in range(1, 17):
            ch_dir = out_root / "mark" / str(ch)
            if not ch_dir.exists():
                continue
            for f in sorted(ch_dir.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                if data["meta"]["confidence"] < args.threshold:
                    low_conf.append({
                        "ref": data["ref"],
                        "confidence": data["meta"]["confidence"],
                        "path": str(f.relative_to(Path("."))),
                    })
        quarantined = []
        q_dir = out_root / "_quarantine"
        if q_dir.exists():
            for f in sorted(q_dir.glob("*.json")):
                quarantined.append(str(f.relative_to(Path("."))))
        report = {
            "threshold": args.threshold,
            "low_confidence_count": len(low_conf),
            "quarantined_count": len(quarantined),
            "low_confidence": low_conf,
            "quarantined": quarantined,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
```

- [ ] **Step 2: Generate the report**

```bash
python scripts/generate_alignments.py --report > data/alignments/_review_report.json
cat data/alignments/_review_report.json | head -40
```

Expected: JSON listing every verse below 0.7 confidence plus anything in `_quarantine/`. Ideally the low-confidence count is small (<20); if it's large, revisit the prompt in `scripts/prompts/align_3way.md` before going further.

- [ ] **Step 3: Write `known-issues.md`**

Populate with the actual content of the report plus any versification notes noticed during ingestion:

```markdown
# Known alignment issues (Mark)

Last updated: 2026-04-22

## Versification mismatches

- **Mark 16:9–20:** The long ending is present in Vulgate and Peshitta but text-critically disputed in Greek NT (bracketed in NA28). We display it aligned; the viewer does NOT currently flag the manuscript dispute.
- **[add more as discovered during generation]**

## Low-confidence alignments

Verses where Claude's self-reported confidence is below 0.7. Flagged for human review; not automatically re-run.

| Ref | Confidence | Note |
|---|---|---|
| [paste rows from `data/alignments/_review_report.json`] | | |

## Quarantined verses

Verses where Claude returned invalid JSON or out-of-bounds token indices even after retry. Listed in `data/alignments/_quarantine/`. Require manual inspection.

| Ref | Reason |
|---|---|
| [fill in if any] | |

## Peshitta enrichment gaps

If ARA's root extractor didn't resolve certain Peshitta words (loanwords, proper nouns), the tooltip for those tokens will be empty. This is expected; the alignment itself is unaffected.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_alignments.py known-issues.md data/alignments/_review_report.json
git commit -m "feat: low-confidence review report + known-issues.md"
```

---

## Phase 6 — Berean benchmark and About page (Tasks 18–19)

### Task 18: About page

**Files:**
- Create: `templates/about.html`
- Modify: `app.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_routes.py`:

```python
def test_about_page_renders(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Methodology" in body or "methodology" in body
    assert "Claude" in body
    assert "STEP Bible" in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_routes.py::test_about_page_renders -v
```
Expected: 404.

- [ ] **Step 3: Add `/about` route to `app.py`**

```python
@app.route("/about")
def about():
    benchmark_path = DATA_DIR / "benchmarks" / "berean_preflight.json"
    benchmark = None
    if benchmark_path.exists():
        benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    return render_template("about.html", benchmark=benchmark)
```

- [ ] **Step 4: Write `templates/about.html`**

```html
{% extends "base.html" %}
{% block title %}About — Translation Alignment{% endblock %}
{% block content %}
<section class="about">
  <h1>Methodology</h1>

  <h2>What this is</h2>
  <p>A parallel viewer for the Gospel of Mark across three text traditions:
  Greek NT (SBLGNT), Syriac Peshitta, and Latin Clementine Vulgate. Each verse's
  word-level alignment was generated offline by Claude, stored as static JSON,
  and is served directly by this read-only app.</p>

  <h2>How alignments were produced</h2>
  <p>All 3-way alignments were generated by Anthropic's Claude Sonnet 4.6 via
  the Batch API. The prompt includes the Greek lemma and morphology from
  STEP Bible's TAGNT (CC BY 4.0) and Peshitta root data from the Aramaic
  Root Atlas. Verses where Claude's self-reported confidence fell below 0.7
  are flagged for human review in the repository's <code>known-issues.md</code>.</p>

  <h2>Methodology validation</h2>
  {% if benchmark %}
    <p>We validated Claude's alignment methodology against the
    <a href="https://biblehub.com/interlinear/mark/">Berean Interlinear</a>
    Greek↔English word alignment. On a sample of
    {{ benchmark.sample_size }} verses in Mark, Claude agreed with Berean's
    word alignment on <strong>{{ "%.1f" | format(benchmark.agreement_rate * 100) }}%</strong>
    of tokens (Berean used only as a benchmark, not as display data). Run on
    {{ benchmark.run_at }} with model <code>{{ benchmark.model }}</code>.</p>
  {% else %}
    <p><em>Benchmark data not yet available.</em></p>
  {% endif %}

  <h2>Attribution</h2>
  <ul>
    <li>Greek NT text: SBLGNT (Society of Biblical Literature Greek New Testament), CC BY 4.0</li>
    <li>Peshitta NT text: via the Aramaic Root Atlas</li>
    <li>Clementine Vulgate: public domain</li>
    <li>Greek-side enrichment (Strong's, lemma, morphology): STEP Bible / Tyndale House Cambridge, CC BY 4.0, via <a href="https://github.com/STEPBible/STEPBible-Data">github.com/STEPBible/STEPBible-Data</a></li>
    <li>Peshitta root data: Aramaic Root Atlas</li>
    <li>Alignment methodology validation: Berean Interlinear (BibleHub)</li>
    <li>Alignment generation: Anthropic Claude Sonnet 4.6</li>
    <li>Viewer inspiration: Prof. Zhang Chen (UIC) — <em>bible-mt5</em> parallel viewer</li>
  </ul>

  <h2>License and reuse</h2>
  <p>This viewer code is open source. The alignment JSON files are derived from
  CC BY 4.0 source data (STEP TAGNT) and public-domain texts; redistribute with
  attribution.</p>
</section>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app.py templates/about.html tests/test_routes.py
git commit -m "feat: about page with methodology and attribution"
```

---

### Task 19: Berean preflight benchmark

**Files:**
- Create: `scripts/run_berean_benchmark.py`
- Create: `data/benchmarks/berean_preflight.json`
- Create: `tests/test_run_berean_benchmark.py`
- Create: `tests/fixtures/berean_mark_sample.json`

**Context:** Berean Interlinear's open data is available as a CSV from biblehub.com (or the `berean-bible` GitHub org). For each Greek token in Mark, it maps to an English gloss. We ask Claude to align Greek↔English for the same verses and compute agreement: for each Greek token, does Claude's English target match Berean's?

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/berean_mark_sample.json`:

```json
{
  "Mark 1:1": [
    {"greek_idx": 0, "greek": "Ἀρχὴ", "english": "[The] beginning"},
    {"greek_idx": 1, "greek": "τοῦ", "english": "of the"},
    {"greek_idx": 2, "greek": "εὐαγγελίου", "english": "gospel"},
    {"greek_idx": 3, "greek": "Ἰησοῦ", "english": "of Jesus"},
    {"greek_idx": 4, "greek": "Χριστοῦ", "english": "Christ"}
  ]
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_run_berean_benchmark.py`:

```python
"""Test Berean benchmark agreement computation."""
import pytest

from scripts.run_berean_benchmark import (
    normalize_gloss,
    compute_agreement,
)


def test_normalize_gloss_strips_brackets_and_lowercases():
    assert normalize_gloss("[The] beginning") == "beginning"
    assert normalize_gloss("of the") == "of the"
    assert normalize_gloss("  God  ") == "god"


def test_compute_agreement_all_match():
    berean = [{"greek_idx": 0, "english": "beginning"},
              {"greek_idx": 1, "english": "gospel"}]
    claude = [{"greek_idx": 0, "english_target": "beginning"},
              {"greek_idx": 1, "english_target": "gospel"}]
    agreement, matched, total = compute_agreement(berean, claude)
    assert matched == 2
    assert total == 2
    assert agreement == 1.0


def test_compute_agreement_partial():
    berean = [{"greek_idx": 0, "english": "beginning"},
              {"greek_idx": 1, "english": "gospel"}]
    claude = [{"greek_idx": 0, "english_target": "start"},
              {"greek_idx": 1, "english_target": "gospel"}]
    agreement, matched, total = compute_agreement(berean, claude)
    assert matched == 1
    assert total == 2
    assert agreement == 0.5


def test_compute_agreement_missing_claude_targets():
    berean = [{"greek_idx": 0, "english": "beginning"}]
    claude = []
    agreement, matched, total = compute_agreement(berean, claude)
    assert matched == 0
    assert total == 1
    assert agreement == 0.0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_run_berean_benchmark.py -v
```
Expected: FAIL on import.

- [ ] **Step 4: Write `scripts/run_berean_benchmark.py`**

```python
"""Run the Berean preflight benchmark: Claude Greek↔English alignment vs Berean.

Emits a single headline agreement rate for display on the About page.

Usage:
    python scripts/run_berean_benchmark.py \\
        --berean tests/fixtures/berean_mark_sample.json \\
        --sample-size 20

(For the full benchmark, supply the full Berean Mark JSON obtained from BibleHub
or a derivative dataset — see known-issues.md for source provenance.)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from translation_core.corpora import CorpusRegistry

logger = logging.getLogger(__name__)

BRACKET_RE = re.compile(r"[\[\]]")


def normalize_gloss(s: str) -> str:
    return BRACKET_RE.sub("", s).strip().lower()


def compute_agreement(berean: list[dict], claude: list[dict]) -> tuple[float, int, int]:
    """For each Berean greek_idx, does claude's english_target match (case-insensitive,
    bracket-stripped)? Return (rate, matched, total).
    """
    total = len(berean)
    if total == 0:
        return (0.0, 0, 0)
    claude_by_idx = {c.get("greek_idx"): c.get("english_target", "") for c in claude}
    matched = 0
    for item in berean:
        bern = normalize_gloss(item.get("english", ""))
        cl = normalize_gloss(claude_by_idx.get(item.get("greek_idx"), ""))
        if not bern or not cl:
            continue
        # Token-level overlap is fine — if ANY word in bern appears in cl or vice versa
        bern_words = set(bern.split())
        cl_words = set(cl.split())
        if bern_words & cl_words:
            matched += 1
    return (matched / total, matched, total)


BENCH_SYSTEM_PROMPT = """You are a biblical text alignment assistant.
Given a Greek verse and an English translation of the same verse, align each
Greek token to its corresponding English word(s). Return JSON:

{"alignment": [{"greek_idx": <int>, "english_target": "<english word(s)>"}, ...]}

Use only the Greek tokens provided. English targets should be 1-3 words each."""


def call_claude_for_bench(client, model: str, greek_tokens: list[str], english_text: str) -> list[dict]:
    user_msg = json.dumps({"greek_tokens": greek_tokens, "english_text": english_text},
                          ensure_ascii=False)
    resp = client.messages.create(
        model=model, max_tokens=1500, temperature=0.1,
        system=BENCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = resp.content[0].text
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json\n"):
            text = text[5:]
    return json.loads(text).get("alignment", [])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--berean", required=True, type=Path,
                    help="Path to Berean Mark alignment JSON (dict keyed by 'Mark 1:1')")
    ap.add_argument("--sample-size", type=int, default=20)
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    berean_all = json.loads(args.berean.read_text(encoding="utf-8"))
    random.seed(args.seed)
    refs = random.sample(list(berean_all.keys()), min(args.sample_size, len(berean_all)))

    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    corpora = CorpusRegistry()
    corpora.add("greek_nt", "Greek NT", args.data_dir / "corpora" / "greek_nt.csv")

    # We also need English — use the WEB (World English Bible) if available,
    # else fall back to Berean's concatenated english glosses.
    web_path = args.data_dir / "corpora" / "web.csv"
    web: dict[str, str] = {}
    if web_path.exists():
        import csv
        with web_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                web[row["reference"]] = row["text"]

    total_matched = 0
    total_tokens = 0
    per_verse = []
    for ref in refs:
        m = re.match(r"(?P<book>.+?)\s+(?P<ch>\d+):(?P<v>\d+)", ref)
        book, ch, v = m.group("book"), int(m.group("ch")), int(m.group("v"))
        greek = corpora.get("greek_nt").get(book, ch, v) or ""
        greek_tokens = greek.split()
        english = web.get(ref) or " ".join(e["english"] for e in berean_all[ref])
        try:
            claude_alignment = call_claude_for_bench(client, args.model, greek_tokens, english)
        except Exception as e:
            logger.warning("%s failed: %s", ref, e)
            continue
        rate, matched, total = compute_agreement(berean_all[ref], claude_alignment)
        per_verse.append({"ref": ref, "rate": rate, "matched": matched, "total": total})
        total_matched += matched
        total_tokens += total
        logger.info("  %s  matched %d/%d (%.2f)", ref, matched, total, rate)

    agreement_rate = total_matched / total_tokens if total_tokens else 0.0
    out = {
        "agreement_rate": agreement_rate,
        "matched_tokens": total_matched,
        "total_tokens": total_tokens,
        "sample_size": len(per_verse),
        "model": args.model,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "per_verse": per_verse,
        "methodology": "Claude aligns Greek tokens to English words; compared against Berean Interlinear gloss overlap (case-insensitive, bracket-stripped, set intersection).",
    }
    out_path = args.data_dir / "benchmarks" / "berean_preflight.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Agreement: %.2f%% across %d tokens in %d verses. Saved to %s",
                agreement_rate * 100, total_tokens, len(per_verse), out_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_run_berean_benchmark.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Obtain Berean source**

Pull Berean Interlinear data (look at `github.com/berean-bible/interlinear-data` or derivative mirrors; if unavailable, scrape from biblehub.com with their permissive terms — document source and license in `known-issues.md`). Transform into the JSON shape our fixture demonstrates (`{"Mark 1:1": [{greek_idx, greek, english}, ...]}`). Save as `data/benchmarks/berean_mark_source.json` (not committed — it's a source artifact, not a deliverable).

- [ ] **Step 7: Run the benchmark**

```bash
python scripts/run_berean_benchmark.py --berean data/benchmarks/berean_mark_source.json --sample-size 20
```

Expected: `data/benchmarks/berean_preflight.json` created with an `agreement_rate` (hopefully >0.85). Cost: ~$0.20 for a 20-verse sample.

- [ ] **Step 8: Smoke-test the About page**

```bash
python app.py
# Visit http://localhost:5000/about — verify the agreement rate renders
```

- [ ] **Step 9: Commit**

```bash
git add scripts/run_berean_benchmark.py tests/test_run_berean_benchmark.py tests/fixtures/berean_mark_sample.json data/benchmarks/berean_preflight.json
git commit -m "feat: Berean Greek↔English preflight benchmark + publish on About"
```

---

## Phase 7 — Viewer polish (Tasks 20–23)

### Task 20: JavaScript — keyboard shortcuts + jump-to-verse + help overlay

**Files:**
- Create: `static/viewer.js`
- Modify: `templates/base.html`
- Modify: `templates/viewer.html`

**Context:** We lean on htmx where possible; this JS is the thin layer for keyboard shortcuts and tooltip wiring. No framework.

- [ ] **Step 1: Write `static/viewer.js`**

```javascript
(function () {
  "use strict";

  // --- Keyboard shortcuts ---
  document.addEventListener("keydown", function (e) {
    // Skip if user is typing in an input or overlay is open
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;

    switch (e.key) {
      case "ArrowRight":
        clickLink(".nav-next");
        break;
      case "ArrowLeft":
        clickLink(".nav-prev");
        break;
      case "j":
        jumpChapter(+1);
        break;
      case "k":
        jumpChapter(-1);
        break;
      case "g":
        openJumpOverlay();
        break;
      case "?":
        openHelpOverlay();
        break;
      case "Escape":
        closeOverlays();
        break;
    }
  });

  function clickLink(selector) {
    const el = document.querySelector(selector);
    if (el && el.tagName === "A") el.click();
  }

  function jumpChapter(delta) {
    const card = document.querySelector(".verse-card");
    if (!card) return;
    const ch = parseInt(card.dataset.chapter, 10);
    const target = ch + delta;
    if (target < 1 || target > 16) return;
    window.location.href = "/mark/" + target + "/1";
  }

  // --- Jump-to-verse overlay ---
  function openJumpOverlay() {
    let overlay = document.getElementById("jump-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "jump-overlay";
      overlay.className = "overlay";
      overlay.innerHTML = `
        <div class="overlay-body">
          <label for="jump-input">Jump to verse</label>
          <input id="jump-input" type="text" placeholder="5:12" autocomplete="off">
          <p class="hint">Format: <code>chapter:verse</code>. Press Enter to go.</p>
        </div>`;
      document.body.appendChild(overlay);
      overlay.querySelector("#jump-input").addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          const m = ev.target.value.match(/^(\d+):(\d+)$/);
          if (m) {
            window.location.href = "/mark/" + m[1] + "/" + m[2];
          }
        } else if (ev.key === "Escape") {
          closeOverlays();
        }
      });
    }
    overlay.classList.add("open");
    overlay.querySelector("#jump-input").focus();
  }

  function openHelpOverlay() {
    let overlay = document.getElementById("help-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "help-overlay";
      overlay.className = "overlay";
      overlay.innerHTML = `
        <div class="overlay-body">
          <h3>Keyboard shortcuts</h3>
          <table>
            <tr><td><kbd>←</kbd> / <kbd>→</kbd></td><td>Previous / next verse</td></tr>
            <tr><td><kbd>j</kbd> / <kbd>k</kbd></td><td>Next / previous chapter</td></tr>
            <tr><td><kbd>g</kbd></td><td>Jump to verse (e.g. <code>5:12</code>)</td></tr>
            <tr><td><kbd>?</kbd></td><td>Show this help</td></tr>
            <tr><td><kbd>Esc</kbd></td><td>Close overlay</td></tr>
          </table>
          <p class="hint">Click a Greek or Peshitta word to see its enrichment tooltip.</p>
        </div>`;
      document.body.appendChild(overlay);
    }
    overlay.classList.add("open");
  }

  function closeOverlays() {
    document.querySelectorAll(".overlay").forEach(o => o.classList.remove("open"));
  }

  // Click outside overlay-body closes it
  document.addEventListener("click", function (e) {
    if (e.target.classList && e.target.classList.contains("overlay")) {
      closeOverlays();
    }
  });

  // --- Tooltips (click-to-open on .tok elements) ---
  document.addEventListener("click", function (e) {
    const tok = e.target.closest(".tok");
    if (!tok) return;
    const tid = tok.dataset.tradition;
    const idx = tok.dataset.idx;
    const card = document.querySelector(".verse-card");
    if (!card) return;
    const ch = card.dataset.chapter;
    const v = card.dataset.verse;

    let endpoint = null;
    if (tid === "greek_nt") endpoint = `/tooltip/greek/${ch}/${v}/${idx}`;
    else if (tid === "peshitta") endpoint = `/tooltip/peshitta/${ch}/${v}/${idx}`;
    if (!endpoint) return;

    fetch(endpoint).then(r => {
      if (r.status !== 200) return "";
      return r.text();
    }).then(html => {
      if (!html) return;
      showTooltip(tok, html);
    });
  });

  function showTooltip(anchor, html) {
    let tip = document.getElementById("active-tooltip");
    if (tip) tip.remove();
    tip = document.createElement("div");
    tip.id = "active-tooltip";
    tip.className = "tooltip";
    tip.innerHTML = html;
    document.body.appendChild(tip);
    const r = anchor.getBoundingClientRect();
    tip.style.left = (window.scrollX + r.left) + "px";
    tip.style.top  = (window.scrollY + r.bottom + 4) + "px";
    // Click anywhere outside closes
    setTimeout(() => {
      document.addEventListener("click", function handler(e) {
        if (!tip.contains(e.target) && !anchor.contains(e.target)) {
          tip.remove();
          document.removeEventListener("click", handler);
        }
      });
    }, 0);
  }
})();
```

- [ ] **Step 2: Add overlay + tooltip CSS to `static/style.css`**

Append:

```css
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: none; align-items: center; justify-content: center; z-index: 1000; }
.overlay.open { display: flex; }
.overlay-body { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 24px; min-width: 300px; max-width: 500px; }
.overlay-body h3 { margin-top: 0; }
.overlay-body table { width: 100%; border-collapse: collapse; }
.overlay-body table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
.overlay-body kbd { background: var(--border); padding: 2px 6px; border-radius: 3px;
  font-family: monospace; }
.overlay-body input { width: 100%; padding: 8px; background: var(--bg);
  color: var(--text); border: 1px solid var(--border); border-radius: 4px;
  font-size: 1.2em; margin-top: 8px; }
.overlay-body .hint { color: var(--muted); font-size: 0.85em; margin-top: 8px; }

.tok { cursor: pointer; }
.tok:hover { background: rgba(125, 211, 252, 0.1); }

.tooltip { position: absolute; background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 12px; max-width: 280px; font-size: 0.9em;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5); z-index: 999; }
.tooltip-inner .tt-token { font-weight: 600; font-size: 1.2em; margin-bottom: 6px; }
.tooltip-inner dl.tt-fields { display: grid; grid-template-columns: auto 1fr;
  gap: 4px 10px; margin: 0; }
.tooltip-inner dt { color: var(--muted); font-size: 0.85em; }
.tooltip-inner dd { margin: 0; }
```

- [ ] **Step 3: Include the script in `templates/base.html`**

Change the `<head>` to add the viewer script at end of body:

Insert before `</body>`:
```html
<script src="{{ url_for('static', filename='viewer.js') }}" defer></script>
```

- [ ] **Step 4: Manual smoke test**

```bash
python app.py
# Visit http://localhost:5000/mark/1/1
# Press → and ← — verify navigation
# Press g, type "5:12", Enter — verify jump
# Press ? — verify help overlay
# Press Esc — verify close
# Click a Greek token — verify tooltip appears with Strong's/morph
# Click a Peshitta token — verify tooltip with root (if peshitta_roots.json populated)
```

- [ ] **Step 5: Commit**

```bash
git add static/viewer.js static/style.css templates/base.html
git commit -m "feat: keyboard shortcuts, jump-to-verse, help overlay, click tooltips"
```

---

### Task 21: Syriac font + RTL robustness

**Files:**
- Create: `static/fonts/EstrangeloEdessa.woff2` (download)
- Create: `static/fonts/LICENSE-SIL-OFL.txt`
- Modify: `static/style.css`

**Context:** Default system fonts often lack full Estrangelo coverage. Self-host the SIL-OFL-licensed Estrangelo Edessa font.

- [ ] **Step 1: Download the font**

Find a WOFF2 build of Estrangelo Edessa (SIL Open Font License). One reliable source: Beth Mardutho's `meltho-fonts` repo, or convert the TTF from [`github.com/sbl/Estrangelo-Edessa`](https://github.com/sbl/Estrangelo-Edessa) using a tool like `woff2_compress`.

```bash
# Example flow (paths depend on where you find the TTF):
mkdir -p static/fonts
# Copy the file into place:
cp /path/to/EstrangeloEdessa.woff2 static/fonts/
# Include the OFL license:
cp /path/to/LICENSE-SIL-OFL.txt static/fonts/
```

- [ ] **Step 2: Add `@font-face` to `static/style.css`**

Insert at the top:

```css
@font-face {
  font-family: "Estrangelo Edessa";
  src: url("/static/fonts/EstrangeloEdessa.woff2") format("woff2");
  font-display: swap;
}
```

- [ ] **Step 3: Manual smoke test**

```bash
python app.py
# In your browser devtools → Network tab: confirm /static/fonts/EstrangeloEdessa.woff2 loads with 200
# Verify the Peshitta column renders with clean Estrangelo letterforms even after disabling system Syriac fonts
```

- [ ] **Step 4: Commit**

```bash
git add static/fonts/
git commit -m "feat: self-hosted Estrangelo Edessa font for Syriac (SIL-OFL)"
```

---

### Task 22: 404 page + error handling

**Files:**
- Create: `templates/404.html`
- Modify: `app.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_routes.py`:

```python
def test_404_page_for_nonexistent_verse(client):
    resp = client.get("/mark/99/99")
    assert resp.status_code == 404
    body = resp.data.decode("utf-8")
    assert "not found" in body.lower()
    assert "/mark/1/1" in body  # link back to a known-good verse
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_routes.py::test_404_page_for_nonexistent_verse -v
```
Expected: 404 returns but body doesn't match ("not found" + /mark/1/1 missing).

- [ ] **Step 3: Write `templates/404.html`**

```html
{% extends "base.html" %}
{% block title %}Not found — Translation Alignment{% endblock %}
{% block content %}
<section class="not-found">
  <h1>Verse not found</h1>
  <p>That chapter and verse aren't in the pilot corpus (Mark only). Try
  <a href="/mark/1/1">Mark 1:1</a> to start reading.</p>
</section>
{% endblock %}
```

- [ ] **Step 4: Register error handler in `app.py`**

Add after the routes:

```python
@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_routes.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app.py templates/404.html tests/test_routes.py
git commit -m "feat: 404 page with link back to Mark 1:1"
```

---

### Task 23: Manual QA pass + QA_LOG.md

**Files:**
- Create: `QA_LOG.md`

**Context:** No new code. Thorough human pass before deployment.

- [ ] **Step 1: Create `QA_LOG.md` as a running checklist**

```markdown
# QA Log — Translation Alignment Viewer MVP

## 2026-04-22 manual pass

Viewer tested at http://localhost:5000.

### Sampled verses
(Pick 10 at random across Mark's 16 chapters; eyeball the alignment and tooltips.)

- [ ] Mark 1:1 — alignment renders; variant underlines visible; Strong's tooltip works
- [ ] Mark 3:27 — ...
- [ ] Mark 5:41 — (Aramaic loanword 'Talitha koum'; verify Peshitta root tooltip)
- [ ] Mark 8:29 — ...
- [ ] Mark 10:45 — ...
- [ ] Mark 13:14 — ...
- [ ] Mark 14:36 — (Aramaic 'Abba'; verify Peshitta root tooltip)
- [ ] Mark 15:34 — (Aramaic retained in Greek; check 3-way alignment for this unusual case)
- [ ] Mark 16:8 — ...
- [ ] Mark 16:20 — (long ending; verify behavior vs. versification note)

### Layout and rendering
- [ ] Desktop (≥1024px) — 3 columns side-by-side
- [ ] Mobile (≤600px) — stacked vertically
- [ ] Syriac column displays RTL; letterforms look correct (self-hosted Estrangelo)
- [ ] Variant underlines visible in both light and dark themes (current build is dark only; flag if theme toggle needed)

### Navigation
- [ ] `→` and `←` arrows move through verses smoothly
- [ ] Chapter boundaries handled (1:last → 2:1 via `→`)
- [ ] `j`/`k` jumps to next/prev chapter
- [ ] `g` opens jump overlay; entering `5:12` navigates correctly
- [ ] `?` opens help overlay; `Esc` closes
- [ ] URL updates correctly during htmx navigation
- [ ] Back/forward browser buttons work

### Tooltips
- [ ] Clicking a Greek word opens the Strong's/morph/lemma/gloss tooltip
- [ ] Clicking a Peshitta word opens the root/sister-root/cognate tooltip
- [ ] Clicking elsewhere closes the tooltip
- [ ] No tooltip on Vulgate words (expected — no enrichment for MVP)

### About page
- [ ] `/about` renders
- [ ] Berean agreement rate is shown with a concrete number
- [ ] All attributions present

### Errors
- [ ] `/mark/99/99` → 404 page with link back to Mark 1:1
- [ ] `/mark/abc/xyz` → 404 or redirect (Flask will 404 on int-typed routes)
- [ ] Alignment missing but corpus present (temporarily delete one JSON; verify "alignment pending" badge)

### Performance
- [ ] Initial page load <500ms on local
- [ ] htmx verse swap <100ms on local

## Issues to address
(Fill in anything failing above; create tasks as needed before deploy.)
```

- [ ] **Step 2: Run through the checklist manually**

Execute each checkbox. For anything that fails, create a follow-up fix commit before moving to Task 24. Document fixes in QA_LOG.md.

- [ ] **Step 3: Commit**

```bash
git add QA_LOG.md
git commit -m "docs: manual QA checklist and pass log"
```

---

## Phase 8 — Deployment (Task 24)

### Task 24: Render deployment

**Files:**
- Create: `render.yaml`
- Modify: `README.md`

- [ ] **Step 1: Write `render.yaml`**

```yaml
services:
  - type: web
    name: translation-alignment
    runtime: python
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
```

Add `gunicorn` to `requirements.txt`:
```
gunicorn==22.0.0
```

- [ ] **Step 2: Update `README.md` with deploy instructions**

Append:

```markdown
## Deploying to Render

1. Push the repo to GitHub.
2. In Render, "New Web Service" → connect the repo.
3. Render detects `render.yaml` automatically; confirm the settings.
4. No environment variables are required at runtime (the `ANTHROPIC_API_KEY` is
   only used by offline scripts, never by the running Flask app).
5. Deploy. The service will come up at `https://translation-alignment.onrender.com`.

## Regenerating alignments

If you edit the prompt or want to refresh the alignment data:

```bash
# Pilot (10 verses, sync API) — use to validate prompt changes cheaply
python scripts/generate_alignments.py --pilot

# Full book via Batch API (50% discount, ~20min wall clock)
python scripts/generate_alignments.py --full

# Report low-confidence + quarantined verses for human review
python scripts/generate_alignments.py --report
```

Each run is idempotent. `git diff` shows what changed.
```

- [ ] **Step 3: Final test before deploy**

```bash
# Reinstall to pick up gunicorn
pip install -r requirements.txt
# Smoke-test under gunicorn (closer to prod)
gunicorn app:app --bind 127.0.0.1:8000
# Visit http://127.0.0.1:8000 — confirm / and /mark/1/1 and /about work
```

- [ ] **Step 4: Deploy**

```bash
git add render.yaml requirements.txt README.md
git commit -m "chore: Render deployment config"
git push -u origin main   # (or your branch, then open a PR)
```

In Render dashboard: new web service → select repo → confirm `render.yaml` → deploy. Monitor the build log.

- [ ] **Step 5: Post-deploy smoke test**

Visit the Render URL. Run through the QA_LOG.md checklist against the deployed instance. Log any environment-specific issues (font CORS, missing env vars) as follow-up commits.

- [ ] **Step 6: Close out**

```bash
# Tag the MVP release
git tag v0.1.0-mvp -m "Translation Alignment Viewer MVP: Mark, Greek/Peshitta/Vulgate"
git push --tags
```

---

## Done criteria for the MVP

Every item from Section 2.3 "Success criteria" in the spec is satisfied:

1. ✅ Viewer loads any verse in Mark in <500ms on Render (verified Task 23 + Task 24 post-deploy)
2. ✅ All ~678 alignment JSONs produced by one repeatable script and reviewable as git diffs (Tasks 15–17)
3. ✅ Berean preflight benchmark publishes a headline agreement rate on `/about` (Task 19)
4. ✅ At least one sample chapter passes a sanity-check read by a human (QA_LOG.md, Task 23)
5. ✅ Syriac RTL + Greek/Latin LTR render correctly desktop and mobile, light and dark (QA_LOG.md, Task 23)

---

## What's NOT in this plan (explicit)

These are parked for Sub-projects 2 & 3 or a later Sub-project 1 iteration (matches the spec's "parked" section):

- Additional books beyond Mark
- Additional traditions (Slavonic, Coptic, Armenian, Chinese, English as 4th column)
- Cross-family root-level diff engine
- Live machine annotation service (Sub-project 2)
- Scholar review queue / approvals / consensus (Sub-project 3)
- User accounts, roles, auth
- TEI XML / BibTeX / CSV export
- In-viewer alignment editing
- Full-text search
- Manuscript variant overlay (Byz vs NA28 vs TR)

If any of these surface as "blocking" during implementation, stop and talk — don't scope-creep them in.
