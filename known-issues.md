# Known Issues / Data Sourcing Notes

## Vulgate (Task 6)

**Source used:** `lat-clementine.usfx.xml` from
<https://github.com/seven1m/open-bibles>
(direct:
<https://raw.githubusercontent.com/seven1m/open-bibles/master/lat-clementine.usfx.xml>).

This is the **Clementine Vulgate** (public domain), verified by hallmark
orthography: punctuation, capitalized proper nouns, `J`/`æ` ligatures
(e.g. "Initium Evangelii Jesu Christi, Filii Dei." at Mark 1:1). It is NOT the
Stuttgart/Weber-Gryson Vulgate, which uses lowercase and no punctuation.

The file is USFX (eBible.org XML). Our `scripts/ingest_vulgate.py` takes an
intermediate TSV (`Book C:V\ttext`) — a helper regex pass in
`/tmp/vulgate_mark.tsv` was produced by walking `<book id="MRK">` / `<c id>` /
`<v id>...<ve/>` markers (see the one-off script referenced in the Task 6 commit
message / git log). If we later need more books, we can generalise that walker
into a `usfx_to_tsv.py` utility.

**Rows extracted:** 677 Mark verses across 16 chapters. The Clementine Vulgate
versification differs from modern editions (NA28) by one or two verses per chapter.
See the Versification Drift section below for the impact on alignment.

## Versification Drift (Vulgate ↔ NA28, Mark)

The Clementine Vulgate's chapter-verse boundaries don't match the NA28 numbering
we use for Greek and Peshitta. Since our pipeline joins the three witnesses by
their numeric verse label, the drift causes whole chapters to misalign.

**Confirmed drift (as of 2026-04-22):**

| Chapter | Vulgate count | NA28 count | Status |
|---|---|---|---|
| Mark 4 | 40 verses | 41 verses | NA28 4:41 has no Vulgate counterpart (Clementine merges 4:40 + 4:41). Marked `absent`. |
| Mark 9 | 49 verses | 50 verses | **RESOLVED 2026-04-22** — see below. |

### Mark 9 drift — RESOLVED 2026-04-22

Clementine Mark 9 was off by one verse throughout: Clementine 9:v carried the
content of NA28 9:v+1, and NA28 9:1 content lived in Clementine **8:39** (not
8:38 as originally suspected — the Clementine versification puts the "some
standing here who will not taste death" saying at the tail of Mark 8, and has
39 verses in Mark 8 vs. NA28's 38).

**Applied:** remapped Clementine 8:39 → Mark 9:1 and Clementine 9:1-49 → Mark
9:2-50 in `data/corpora/vulgate.csv`, dropped the orphaned Vulgate 8:39 row,
deleted all Mark 9 alignments, and regenerated 50 via Batch API. Low-confidence
Mark 9 verses collapsed from 21 → 0. Reusable helper:
`scripts/extract_vulgate_range.py`.

**Workaround still in place for Mark 4:41:** Prompt instructs the model to skip
any tradition with zero tokens (rule 8 in `scripts/prompts/align_3way.md`). This
handles the Mark 4:41 absent case.

## Peshitta root tooltip (ARA adapter) — RESOLVED 2026-04-22

Earlier builds of `scripts/snapshot_ara_roots.py` emitted a stub where every
Peshitta token had `root: null`, so the viewer's tooltips all showed "Root: —".
The adapter tried to instantiate ARA's `RootExtractor()` with no arguments, but
`RootExtractor.__init__(corpus, data_dir=None)` requires a populated
`AramaicCorpus`.

**Applied:** the script now mirrors ARA's own `app.py::_init()` — builds an
`AramaicCorpus` from the sibling repo's `data/corpora/peshitta_nt.csv` (+ OT and
Biblical Aramaic if present), calls `RootExtractor.build_index()`, loads
`CognateLookup` from `data/roots/cognates.json`, and per token emits a
Latin-transliterated root key (e.g. `r-sh-a`), sister roots (keys sharing ≥2
positions, the same heuristic ARA's UI uses), and first Hebrew/Arabic cognate
words. Result: 6,760 / 8,793 Mark tokens (~77%) now have real root + cognate
data. The remainder are proper nouns, Greek loan-words, and short particles
ARA's extractor intentionally skips (stop-words, hyphenated forms).

## (Reserved)

Other sourcing / data gaps will be logged here as they come up.
