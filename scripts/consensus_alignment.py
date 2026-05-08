"""Build a consensus alignment corpus from N independent runs.

Given two or more roots (each laid out as `<root>/mark/<ch>/<v>.json`),
emit per-verse consensus artifacts that keep only the alignment groups
where all runs agree on token-set membership across all three traditions.
For shared groups, also report whether verdict (`variant`) and type
agree across runs.

Usage:
    PYTHONPATH=. python scripts/consensus_alignment.py \\
        --root data/alignments \\
        --root data/_compare/sonnet_run2/alignments \\
        --book mark \\
        --out  data/_compare/consensus/alignments \\
        --report-md docs/sonnet-consensus-mark.md

Output:
    --out/<book>/<ch>/<v>.json — consensus alignment (intersection of groups)
    --report-md                — human-readable Markdown summary
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def members_key(g: dict) -> tuple:
    """Two alignment groups across runs are 'the same' if they cover the
    same token-index set across all three traditions."""
    return (
        tuple(sorted(g.get("greek_nt", []))),
        tuple(sorted(g.get("peshitta", []))),
        tuple(sorted(g.get("vulgate", []))),
    )


def load_chapter(root: Path, book: str, chapter: int) -> dict[int, dict]:
    out: dict[int, dict] = {}
    ch_dir = root / book / str(chapter)
    if not ch_dir.exists():
        return out
    for f in sorted(ch_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out[int(f.stem)] = data
        except Exception:
            pass
    return out


def consensus_for_verse(runs: list[dict]) -> tuple[dict, dict]:
    """Return (consensus_verse_dict, stats_dict).

    The consensus verse keeps only groups whose membership-key appears
    in every run. For each kept group, we record the per-run verdict /
    type / note so callers can inspect agreement.
    """
    if not runs:
        return {}, {"verses": 0}

    # Use run[0] as the spine for ref/chapter/verse/traditions
    spine = runs[0]
    keys_per_run = [set(members_key(g) for g in r.get("alignment", [])) for r in runs]
    common_keys = set.intersection(*keys_per_run)

    # For each common key, gather the group from each run for inspection
    consensus_groups: list[dict] = []
    variant_agreements = 0
    type_agreements = 0
    for k in common_keys:
        per_run_groups = []
        for r in runs:
            for g in r.get("alignment", []):
                if members_key(g) == k:
                    per_run_groups.append(g)
                    break
        # Decide consensus verdict: if all runs agree, use that. Else flag.
        variants = [g.get("variant") for g in per_run_groups]
        types = [g.get("type") for g in per_run_groups]
        all_variant_agree = len(set(variants)) == 1
        all_type_agree = len(set(types)) == 1
        if all_variant_agree:
            variant_agreements += 1
        if all_type_agree:
            type_agreements += 1
        # Use run #0's group as the canonical record, but tag with consensus quality.
        canonical = dict(per_run_groups[0])
        canonical["_consensus"] = {
            "runs_agree_variant": all_variant_agree,
            "runs_agree_type": all_type_agree,
            "variants_per_run": variants,
            "types_per_run": types,
        }
        consensus_groups.append(canonical)

    # Sort by greek index for stable output
    consensus_groups.sort(key=lambda g: (g.get("greek_nt") or [9999], g.get("peshitta") or [9999]))

    out = {
        "ref": spine.get("ref"),
        "chapter": spine.get("chapter"),
        "verse": spine.get("verse"),
        "traditions": spine.get("traditions"),
        "alignment": consensus_groups,
        "meta": {
            "generated_by": f"consensus-of-{len(runs)}",
            "runs": [r.get("meta", {}).get("generated_by") for r in runs],
            "schema_version": 1,
            "consensus_quality": {
                "groups_in_consensus": len(consensus_groups),
                "variant_agreement_count": variant_agreements,
                "type_agreement_count": type_agreements,
            },
        },
    }
    stats = {
        "ref": spine.get("ref"),
        "groups_per_run": [len(r.get("alignment", [])) for r in runs],
        "groups_in_consensus": len(consensus_groups),
        "variant_full_agreement": variant_agreements,
        "type_full_agreement": type_agreements,
    }
    return out, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True,
                    help="Repeat for each input run (≥ 2)")
    ap.add_argument("--book", default="mark")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output root for consensus alignment JSONs")
    ap.add_argument("--report-md", type=Path, required=True,
                    help="Where to write the Markdown summary")
    args = ap.parse_args()

    if len(args.root) < 2:
        ap.error("Pass --root at least twice (need ≥ 2 runs to compute consensus)")
    roots = [Path(r) for r in args.root]
    for r in roots:
        if not (r / args.book).exists():
            print(f"ERROR: {r}/{args.book}/ does not exist", file=sys.stderr)
            return 1

    # Discover chapters present in ALL runs
    chapter_sets = []
    for r in roots:
        chs = set()
        for d in (r / args.book).iterdir():
            if d.is_dir() and d.name.isdigit():
                chs.add(int(d.name))
        chapter_sets.append(chs)
    common_chapters = sorted(set.intersection(*chapter_sets))

    # Per-verse consensus
    all_stats: list[dict] = []
    verses_with_consensus = 0
    verses_only_in_subset = 0
    for ch in common_chapters:
        per_run_chapter = [load_chapter(r, args.book, ch) for r in roots]
        # Verses that appear in all runs
        common_verses = sorted(set.intersection(*(set(d) for d in per_run_chapter)))
        for v in common_verses:
            runs = [per_run_chapter[i][v] for i in range(len(roots))]
            out, stats = consensus_for_verse(runs)
            stats["chapter"] = ch
            stats["verse"] = v
            all_stats.append(stats)
            # Write
            out_path = args.out / args.book / str(ch) / f"{v}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            verses_with_consensus += 1
        # Verses present in some runs but not all (lost to disagreement-on-existence)
        union_verses = set.union(*(set(d) for d in per_run_chapter))
        verses_only_in_subset += len(union_verses - set(common_verses))

    # Aggregate
    total_groups_run0 = sum(s["groups_per_run"][0] for s in all_stats)
    total_groups_run1 = sum(s["groups_per_run"][1] for s in all_stats)
    total_consensus = sum(s["groups_in_consensus"] for s in all_stats)
    total_variant_agree = sum(s["variant_full_agreement"] for s in all_stats)
    total_type_agree = sum(s["type_full_agreement"] for s in all_stats)

    pct_consensus_vs_run0 = round(100 * total_consensus / total_groups_run0, 1) if total_groups_run0 else 0
    pct_consensus_vs_run1 = round(100 * total_consensus / total_groups_run1, 1) if total_groups_run1 else 0
    pct_variant_agree = round(100 * total_variant_agree / total_consensus, 1) if total_consensus else 0
    pct_type_agree = round(100 * total_type_agree / total_consensus, 1) if total_consensus else 0

    # Verdict / type agreement distributions across consensus groups
    variant_agree_per_verse = Counter()
    type_agree_per_verse = Counter()
    for s in all_stats:
        ratio_v = s["variant_full_agreement"] / s["groups_in_consensus"] if s["groups_in_consensus"] else 0
        ratio_t = s["type_full_agreement"] / s["groups_in_consensus"] if s["groups_in_consensus"] else 0
        variant_agree_per_verse[round(ratio_v, 1)] += 1
        type_agree_per_verse[round(ratio_t, 1)] += 1

    # Markdown report
    lines: list[str] = []
    lines.append("# Sonnet Consensus Corpus — Mark")
    lines.append("")
    lines.append("Methodology audit + consensus subset of two independent Sonnet 4.5 runs.")
    lines.append("")
    lines.append("## What this is")
    lines.append("")
    lines.append("Two independent runs of the same prompt against the same input data, on")
    lines.append("`claude-sonnet-4-5` via Batch API, produce alignment artifacts that often")
    lines.append("disagree (see `docs/sonnet-vs-opus-mark13.md` for the cross-model audit).")
    lines.append("This consensus corpus keeps only the alignment groups where **both runs")
    lines.append("agree on the token-set partition** — i.e. both runs decided that the same")
    lines.append("Greek tokens, Peshitta tokens, and Vulgate tokens belong together as a")
    lines.append("single alignment group. For each kept group, we additionally record whether")
    lines.append("the runs agree on the verdict (`aligned`/`minor`/`major`/`omitted`/`added`)")
    lines.append("and the semantic type (`harmonisation`/`substitution`/...).")
    lines.append("")
    lines.append("**The result is a smaller but more defensible corpus**: every group that")
    lines.append("survives appears in two independent samples from the model. Groups that")
    lines.append("only appeared in one run are dropped — they are exactly the unstable claims.")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Verses with both runs available | {verses_with_consensus} |")
    lines.append(f"| Verses that appear in only one run (dropped) | {verses_only_in_subset} |")
    lines.append(f"| Run #1 (production) total groups | {total_groups_run0} |")
    lines.append(f"| Run #2 total groups | {total_groups_run1} |")
    lines.append(f"| Consensus groups (membership match) | {total_consensus} |")
    lines.append(f"| Consensus / run #1 | {pct_consensus_vs_run0}% |")
    lines.append(f"| Consensus / run #2 | {pct_consensus_vs_run1}% |")
    lines.append(f"| Of consensus groups: full variant agreement | {total_variant_agree} ({pct_variant_agree}%) |")
    lines.append(f"| Of consensus groups: full type agreement | {total_type_agree} ({pct_type_agree}%) |")
    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append("- **Consensus / run #1**: of the alignment groups in the original")
    lines.append("  production corpus, how many survived the consensus filter. Groups")
    lines.append("  unique to one run are unstable claims and were dropped.")
    lines.append("- **Variant agreement**: of the groups that DID survive (both runs")
    lines.append("  agreed on tokens), how often did they also agree on the verdict.")
    lines.append("  Disagreement here is rare but real — a group both runs decided was")
    lines.append("  the same alignment but disagreed on whether it's `aligned` or `minor`.")
    lines.append("- **Type agreement**: same, for the semantic type field. Lower agreement")
    lines.append("  (the type vocabulary has 12 categories, finer-grained than verdict).")
    lines.append("")
    lines.append("## Distribution: variant agreement per verse")
    lines.append("")
    lines.append("| Agreement ratio | Verses |")
    lines.append("|---|---|")
    for ratio in sorted(variant_agree_per_verse, reverse=True):
        lines.append(f"| {int(ratio*100)}% | {variant_agree_per_verse[ratio]} |")
    lines.append("")
    lines.append("## Output layout")
    lines.append("")
    lines.append("Each consensus verse JSON keeps the schema of the original alignment")
    lines.append("artifacts but adds a `_consensus` block per group that records:")
    lines.append("  - `runs_agree_variant`: did all runs assign the same verdict")
    lines.append("  - `runs_agree_type`: did all runs assign the same type")
    lines.append("  - `variants_per_run`, `types_per_run`: the per-run values")
    lines.append("")
    lines.append("Top-level `meta` records `generated_by: 'consensus-of-N'` and the")
    lines.append("contributing run identifiers.")
    lines.append("")
    lines.append("## Practical use")
    lines.append("")
    lines.append("- **For citation**: prefer the consensus subset over the single-run")
    lines.append("  corpus. Each consensus group has been corroborated by an independent")
    lines.append("  re-run, which is a weak but defensible reproducibility signal.")
    lines.append("- **For review prioritization**: the groups that did NOT make consensus")
    lines.append("  (only appearing in one run) are the natural target for human review.")
    lines.append("  Roughly half the original corpus, focused on exactly the unstable claims.")
    lines.append("- **For headline counts**: the production corpus reports 8,206 alignment")
    lines.append("  groups; the consensus subset is substantially smaller. Cite both numbers")
    lines.append("  honestly: \"X consensus groups across Y verses, dropped from a single-run")
    lines.append("  corpus of Z groups due to inter-run disagreement.\"")
    lines.append("")
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {verses_with_consensus} consensus verses to {args.out}", file=sys.stderr)
    print(f"Wrote report to {args.report_md}", file=sys.stderr)
    print(f"Headline: {total_consensus} consensus groups (Run#1 {total_groups_run0}, Run#2 {total_groups_run1})", file=sys.stderr)
    print(f"  → consensus = {pct_consensus_vs_run0}% of run#1, {pct_consensus_vs_run1}% of run#2", file=sys.stderr)
    print(f"  → variant agreement: {pct_variant_agree}%, type agreement: {pct_type_agree}%", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
