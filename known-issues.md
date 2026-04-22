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

| Chapter | Vulgate count | NA28 count | Effect |
|---|---|---|---|
| Mark 4 | 40 verses | 41 verses | NA28 4:41 has no Vulgate counterpart (Clementine merges 4:40 + 4:41). Now marked `absent` correctly. |
| Mark 9 | 49 verses | 50 verses | **Off-by-one across the whole chapter.** Vulgate 9:v → NA28 9:v+1. NA28 9:1 content is in Clementine 8:38 (we don't currently ingest Mark 8, so it's missing). |
| Mark 9:50 | absent | 9:50 | Content is in Clementine 9:49. Now marked `absent` pending re-shift. |

**Consequences:** All 21 verses in Mark 9 came out of the Batch API re-run with
confidence < 0.7 because Claude correctly detected that the Vulgate content
doesn't match the Greek + Peshitta content for the same verse label. The
alignment pipeline is doing the right thing — the data fed in is wrong.

**Proper fix (not yet applied):**
1. Re-ingest Vulgate Mark 8 (to pick up Clementine 8:38 = NA28 9:1 content)
2. Shift Vulgate Mark 9 verse labels by +1 (so Vulgate 9:1 → NA28 9:2, etc.)
3. Map Clementine 8:38 to NA28 9:1 explicitly
4. Delete Mark 9 alignments and regenerate (50 verses via batch ≈ $0.50)

Rough cost estimate for the full fix: ~$1 + 20 min wall clock.

**Workaround in place:** Prompt now explicitly instructs the model to skip any
tradition with zero tokens (rule 8 in `scripts/prompts/align_3way.md`). This
successfully handles the Mark 4:41 and 9:50 absent cases. It does not fix the
Mark 9 drift — those verses are "present but wrong."

## (Reserved)

Other sourcing / data gaps will be logged here as they come up.
