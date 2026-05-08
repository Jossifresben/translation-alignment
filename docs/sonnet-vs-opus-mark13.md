# Sonnet vs Opus — Mark 13

Comparison of two independent runs of the alignment-generation
pipeline against the same corpus, same prompt, same enrichment data.
Sample: Mark 13, 36 verses.

## Aggregate

| Metric | Value |
|---|---|
| Verses compared | 36 |
| Sonnet alignment groups (total) | 347 |
| Opus alignment groups (total) | 373 |
| Group-membership overlap | 180 (48.3%) |
| Groups only in Sonnet | 167 |
| Groups only in Opus | 193 |
| Variant agreement (within shared groups) | 127/180 (70.6%) |
| Type agreement (within shared groups) | 72/180 (40.0%) |
| Avg apparatus-note similarity (Levenshtein ratio) | 0.168 |
| Avg Sonnet self-confidence | 0.878 |
| Avg Opus self-confidence | 0.898 |

## Per-verse

| Verse | S grp | O grp | shared | only-S | only-O | variant δ | type δ | note sim | S conf | O conf |
|---|---|---|---|---|---|---|---|---|---|---|
| Mark 13:1 | 10 | 11 | 5 | 5 | 6 | 3 | 4 | 0.115 | 0.88 | 0.88 |
| Mark 13:2 | 10 | 22 | 3 | 7 | 19 | 0 | 1 | 0.266 | 0.88 | 0.92 |
| Mark 13:3 | 15 | 15 | 0 | 15 | 15 | 0 | 0 | — | 0.88 | 0.88 |
| Mark 13:4 | 8 | 14 | 4 | 4 | 10 | 0 | 4 | — | 0.82 | 0.92 |
| Mark 13:5 | 8 | 11 | 3 | 5 | 8 | 3 | 2 | 0.035 | 0.9 | 0.92 |
| Mark 13:6 | 11 | 8 | 5 | 6 | 3 | 1 | 4 | 0.236 | 0.88 | 0.92 |
| Mark 13:7 | 12 | 11 | 6 | 6 | 5 | 2 | 1 | 0.186 | 0.88 | 0.88 |
| Mark 13:8 | 8 | 19 | 2 | 6 | 17 | 1 | 2 | 0.16 | 0.88 | 0.82 |
| Mark 13:9 | 9 | 11 | 2 | 7 | 9 | 0 | 0 | 0.0 | 0.88 | 0.88 |
| Mark 13:10 | 7 | 7 | 7 | 0 | 0 | 1 | 2 | 0.174 | 0.88 | 0.88 |
| Mark 13:11 | 12 | 15 | 4 | 8 | 11 | 2 | 2 | 0.18 | 0.88 | 0.88 |
| Mark 13:12 | 15 | 14 | 5 | 10 | 9 | 3 | 2 | 0.17 | 0.88 | 0.92 |
| Mark 13:13 | 9 | 7 | 3 | 6 | 4 | 0 | 1 | 0.244 | 0.88 | 0.92 |
| Mark 13:14 | 11 | 14 | 8 | 3 | 6 | 0 | 5 | 0.201 | 0.88 | 0.82 |
| Mark 13:15 | 10 | 7 | 4 | 6 | 3 | 0 | 2 | 0.306 | 0.82 | 0.88 |
| Mark 13:16 | 5 | 6 | 4 | 1 | 2 | 1 | 3 | 0.139 | 0.88 | 0.92 |
| Mark 13:17 | 6 | 6 | 5 | 1 | 1 | 1 | 4 | 0.153 | 0.88 | 0.92 |
| Mark 13:18 | 6 | 6 | 6 | 0 | 0 | 3 | 5 | 0.091 | 0.82 | 0.82 |
| Mark 13:19 | 13 | 11 | 7 | 6 | 4 | 2 | 5 | 0.104 | 0.88 | 0.92 |
| Mark 13:20 | 12 | 11 | 5 | 7 | 6 | 2 | 3 | 0.122 | 0.88 | 0.92 |
| Mark 13:21 | 11 | 11 | 6 | 5 | 5 | 4 | 3 | 0.322 | 0.88 | 0.92 |
| Mark 13:22 | 10 | 14 | 4 | 6 | 10 | 1 | 2 | 0.19 | 0.88 | 0.92 |
| Mark 13:23 | 7 | 7 | 7 | 0 | 0 | 1 | 4 | 0.215 | 0.9 | 0.92 |
| Mark 13:25 | 8 | 4 | 1 | 7 | 3 | 0 | 0 | 0.305 | 0.88 | 0.92 |
| Mark 13:26 | 7 | 7 | 7 | 0 | 0 | 3 | 3 | 0.175 | 0.88 | 0.92 |
| Mark 13:27 | 11 | 9 | 6 | 5 | 3 | 3 | 4 | 0.195 | 0.88 | 0.88 |
| Mark 13:28 | 13 | 18 | 4 | 9 | 14 | 1 | 2 | 0.2 | 0.88 | 0.88 |
| Mark 13:29 | 10 | 11 | 8 | 2 | 3 | 1 | 6 | 0.135 | 0.88 | 0.88 |
| Mark 13:30 | 11 | 11 | 8 | 3 | 3 | 2 | 6 | 0.144 | 0.88 | 0.92 |
| Mark 13:31 | 8 | 6 | 4 | 4 | 2 | 0 | 3 | 0.118 | 0.9 | 0.92 |
| Mark 13:32 | 8 | 8 | 8 | 0 | 0 | 2 | 4 | 0.14 | 0.9 | 0.92 |
| Mark 13:33 | 12 | 6 | 3 | 9 | 3 | 0 | 3 | — | 0.88 | 0.92 |
| Mark 13:34 | 9 | 9 | 8 | 1 | 1 | 4 | 6 | 0.129 | 0.88 | 0.82 |
| Mark 13:35 | 12 | 12 | 8 | 4 | 4 | 1 | 2 | 0.111 | 0.88 | 0.92 |
| Mark 13:36 | 6 | 6 | 4 | 2 | 2 | 1 | 3 | 0.222 | 0.9 | 0.92 |
| Mark 13:37 | 7 | 8 | 6 | 1 | 2 | 4 | 5 | 0.069 | 0.88 | 0.92 |

## How to read this

- **Group-membership overlap**: out of all the alignment groups produced by
  either run, how many had identical token-set membership across all three
  witnesses. This is the most fundamental agreement metric — if the two runs
  don't even agree on *which tokens align*, downstream verdict/type comparisons
  are meaningless.
- **Variant / type agreement**: of the groups that *do* share membership, how
  often do both runs assign the same `variant` verdict (aligned / minor / major /
  omitted / added) and the same `type` (harmonisation / substitution / ...).
- **Note similarity**: a Levenshtein ratio (0–1) between the two runs' apparatus
  prose for the same group. 1.0 = identical text; ~0.4 = same idea, different
  wording; <0.2 = substantively different claims.
- **Confidence**: each model's own self-reported confidence, NOT a calibration
  metric. Compare the two as a sanity check on relative certainty.
