"""Compare Sonnet- and Opus-generated alignments verse-by-verse.

Reads the production Sonnet corpus from `data/alignments/mark/` and a parallel
Opus corpus from a `--opus-root`, then emits a Markdown report summarizing:

  - Per-verse: alignment-group count, verdict / type / membership disagreements,
    apparatus-note prose differences (Levenshtein-ratio based).
  - Aggregate: overall agreement rate, per-variant-type breakdown.

Usage:
    PYTHONPATH=. python scripts/compare_sonnet_opus.py \\
        --sonnet-root data/alignments \\
        --opus-root   data/_compare/opus_mark13/alignments \\
        --chapter     13 \\
        --out         docs/sonnet-vs-opus-mark13.md
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path


def load_chapter(root: Path, chapter: int) -> dict[int, dict]:
    """Return {verse_number: alignment_dict} for one chapter, or {} if missing."""
    out: dict[int, dict] = {}
    ch_dir = root / "mark" / str(chapter)
    if not ch_dir.exists():
        return out
    for f in sorted(ch_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        v = int(f.stem)
        out[v] = data
    return out


def members_key(g: dict) -> tuple:
    """Two alignment groups are "the same" if they cover the same set of token
    indices across all three traditions. Tradition keys (greek_nt/peshitta/
    vulgate) are at the top level of each group in the canonical schema."""
    return (
        tuple(sorted(g.get("greek_nt", []))),
        tuple(sorted(g.get("peshitta", []))),
        tuple(sorted(g.get("vulgate", []))),
    )


def compare_verse(s: dict, o: dict) -> dict:
    """Compare one verse's Sonnet vs Opus alignment artifacts."""
    s_groups = s.get("alignment", [])
    o_groups = o.get("alignment", [])

    # Multiple groups can share the same membership key only in pathological
    # cases (would mean both groups cover identical tokens) — we rely on
    # uniqueness here, dropping duplicates if any.
    s_by_key = {members_key(g): g for g in s_groups}
    o_by_key = {members_key(g): g for g in o_groups}

    s_keys = set(s_by_key)
    o_keys = set(o_by_key)
    shared = s_keys & o_keys
    only_sonnet = s_keys - o_keys
    only_opus = o_keys - s_keys

    # For groups with matching membership: how often do variant/type/note differ?
    # Schema fields: `variant` (the verdict: aligned/minor/major/omitted/added),
    # `type` (semantic type — present on non-aligned groups), `note` (apparatus
    # prose — present on non-aligned groups).
    variant_disagreement = 0
    type_disagreement = 0
    note_similarity_sum = 0.0
    note_pairs = 0
    for k in shared:
        sg = s_by_key[k]
        og = o_by_key[k]
        if sg.get("variant") != og.get("variant"):
            variant_disagreement += 1
        # `type` may be absent on `aligned` groups; treat absent as None
        if sg.get("type") != og.get("type"):
            type_disagreement += 1
        sn = (sg.get("note") or "").strip()
        on = (og.get("note") or "").strip()
        if sn or on:
            ratio = difflib.SequenceMatcher(None, sn, on).ratio()
            note_similarity_sum += ratio
            note_pairs += 1

    return {
        "ref": s.get("ref") or o.get("ref"),
        "sonnet_groups": len(s_groups),
        "opus_groups": len(o_groups),
        "shared_groups": len(shared),
        "only_sonnet_groups": len(only_sonnet),
        "only_opus_groups": len(only_opus),
        "variant_disagreement": variant_disagreement,
        "type_disagreement": type_disagreement,
        "note_avg_similarity": round(note_similarity_sum / note_pairs, 3) if note_pairs else None,
        "note_pairs_compared": note_pairs,
        "sonnet_confidence": s.get("meta", {}).get("confidence"),
        "opus_confidence": o.get("meta", {}).get("confidence"),
    }


def fmt_md(rows: list[dict], chapter: int) -> str:
    if not rows:
        return f"# Sonnet vs Opus — Mark {chapter}\n\nNo data.\n"

    # Aggregates
    total_s = sum(r["sonnet_groups"] for r in rows)
    total_o = sum(r["opus_groups"] for r in rows)
    total_shared = sum(r["shared_groups"] for r in rows)
    total_only_s = sum(r["only_sonnet_groups"] for r in rows)
    total_only_o = sum(r["only_opus_groups"] for r in rows)
    total_variant_d = sum(r["variant_disagreement"] for r in rows)
    total_type_d = sum(r["type_disagreement"] for r in rows)
    note_sims = [r["note_avg_similarity"] for r in rows if r["note_avg_similarity"] is not None]
    avg_note_sim = round(sum(note_sims) / len(note_sims), 3) if note_sims else None
    avg_s_conf = round(sum(r["sonnet_confidence"] or 0 for r in rows) / len(rows), 3)
    avg_o_conf = round(sum(r["opus_confidence"] or 0 for r in rows) / len(rows), 3)

    pct_membership_match = round(100 * total_shared / max(total_s, total_o), 1)
    pct_variant_match = (
        round(100 * (total_shared - total_variant_d) / total_shared, 1)
        if total_shared else 0
    )
    pct_type_match = (
        round(100 * (total_shared - total_type_d) / total_shared, 1)
        if total_shared else 0
    )

    lines: list[str] = []
    lines.append(f"# Sonnet vs Opus — Mark {chapter}")
    lines.append("")
    lines.append("Comparison of two independent runs of the alignment-generation")
    lines.append("pipeline against the same corpus, same prompt, same enrichment data.")
    lines.append(f"Sample: Mark {chapter}, {len(rows)} verses.")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Verses compared | {len(rows)} |")
    lines.append(f"| Sonnet alignment groups (total) | {total_s} |")
    lines.append(f"| Opus alignment groups (total) | {total_o} |")
    lines.append(f"| Group-membership overlap | {total_shared} ({pct_membership_match}%) |")
    lines.append(f"| Groups only in Sonnet | {total_only_s} |")
    lines.append(f"| Groups only in Opus | {total_only_o} |")
    lines.append(f"| Variant agreement (within shared groups) | {total_shared - total_variant_d}/{total_shared} ({pct_variant_match}%) |")
    lines.append(f"| Type agreement (within shared groups) | {total_shared - total_type_d}/{total_shared} ({pct_type_match}%) |")
    if avg_note_sim is not None:
        lines.append(f"| Avg apparatus-note similarity (Levenshtein ratio) | {avg_note_sim} |")
    lines.append(f"| Avg Sonnet self-confidence | {avg_s_conf} |")
    lines.append(f"| Avg Opus self-confidence | {avg_o_conf} |")
    lines.append("")
    lines.append("## Per-verse")
    lines.append("")
    lines.append("| Verse | S grp | O grp | shared | only-S | only-O | variant δ | type δ | note sim | S conf | O conf |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        sim = f"{r['note_avg_similarity']}" if r["note_avg_similarity"] is not None else "—"
        lines.append(
            f"| {r['ref']} "
            f"| {r['sonnet_groups']} | {r['opus_groups']} | {r['shared_groups']} "
            f"| {r['only_sonnet_groups']} | {r['only_opus_groups']} "
            f"| {r['variant_disagreement']} | {r['type_disagreement']} "
            f"| {sim} "
            f"| {r['sonnet_confidence']} | {r['opus_confidence']} |"
        )
    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append("- **Group-membership overlap**: out of all the alignment groups produced by")
    lines.append("  either run, how many had identical token-set membership across all three")
    lines.append("  witnesses. This is the most fundamental agreement metric — if the two runs")
    lines.append("  don't even agree on *which tokens align*, downstream verdict/type comparisons")
    lines.append("  are meaningless.")
    lines.append("- **Variant / type agreement**: of the groups that *do* share membership, how")
    lines.append("  often do both runs assign the same `variant` verdict (aligned / minor / major /")
    lines.append("  omitted / added) and the same `type` (harmonisation / substitution / ...).")
    lines.append("- **Note similarity**: a Levenshtein ratio (0–1) between the two runs' apparatus")
    lines.append("  prose for the same group. 1.0 = identical text; ~0.4 = same idea, different")
    lines.append("  wording; <0.2 = substantively different claims.")
    lines.append("- **Confidence**: each model's own self-reported confidence, NOT a calibration")
    lines.append("  metric. Compare the two as a sanity check on relative certainty.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonnet-root", type=Path, default=Path("data/alignments"))
    ap.add_argument("--opus-root", type=Path, required=True)
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    sonnet = load_chapter(args.sonnet_root, args.chapter)
    opus = load_chapter(args.opus_root, args.chapter)

    if not sonnet:
        print(f"ERROR: no Sonnet data at {args.sonnet_root}/mark/{args.chapter}", file=sys.stderr)
        return 1
    if not opus:
        print(f"ERROR: no Opus data at {args.opus_root}/mark/{args.chapter}", file=sys.stderr)
        return 1

    common_verses = sorted(set(sonnet) & set(opus))
    rows = [compare_verse(sonnet[v], opus[v]) for v in common_verses]

    md = fmt_md(rows, args.chapter)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"Wrote {args.out} with {len(rows)} verses", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
