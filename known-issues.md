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
versification differs from modern editions by one or two verses per chapter
(e.g. Mark 4 has 40 vs. modern 41, Mark 8 has 39 vs. modern 38) — this matches
other Clementine sources and is not a loss.

## (Reserved)

Other sourcing / data gaps will be logged here as they come up.
