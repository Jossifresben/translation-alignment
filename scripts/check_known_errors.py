"""Check whether a model run avoids the apparatus errors caught in the
2026-04-30 self-audit.

We have a tiny ground-truth set: four apparatus claims that a human
verified were WRONG in the production Sonnet corpus (see
data/alignments/CHANGELOG.md, v1.0.0 patches). This script checks, for a
given alignment root, whether the model's output for those verses
*repeats* the error or *avoids* it.

This is a weak but real directional-accuracy signal — the only ground
truth we have that isn't "another model's opinion."

Usage:
    PYTHONPATH=. python scripts/check_known_errors.py \\
        --root data/_compare/opus48_mark13_run1/alignments \\
        --label "Opus 4.8 run 1"

Each known error is encoded as: a verse, a set of token indices that
identify the relevant alignment group (matched by membership overlap),
and a predicate that returns True if the note/verdict REPEATS the error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Patch notes in the production corpus document the original error inside a
# "[Patched in corpus vX — original output ...]" bracket for transparency.
# That audit text would trip the error predicates (it quotes the mistake),
# so we strip it before checking. Fresh model runs have no such bracket.
_PATCH_BRACKET = re.compile(r"\[Patched[^\]]*\]")


def _norm(s) -> str:
    s = s or ""
    s = _PATCH_BRACKET.sub("", s)
    return s.lower()


# Each check: (chapter, verse, locator_token_sets, repeats_error_fn, description)
# locator: we find the group whose Greek index set best overlaps the locator;
# the predicate inspects that group's note/variant/type.
KNOWN_ERRORS = [
    {
        "ref": "Mark 13:14",
        "chapter": 13, "verse": 14,
        # The βδέλυγμα τῆς ἐρημώσεως group; Greek indices ~3-6
        "greek_locator": [3, 4, 5, 6],
        "repeats_error": lambda g: "demonstrative pronoun" in _norm(g.get("note")),
        "desc": "ܐܬܐ mis-classified as a demonstrative pronoun (it is a noun, 'sign')",
    },
    {
        "ref": "Mark 1:1",
        "chapter": 1, "verse": 1,
        # τοῦ εὐαγγελίου group; Greek indices ~1-2
        "greek_locator": [1, 2],
        "repeats_error": lambda g: "construct state" in _norm(g.get("note")),
        "desc": "Peshitta ܕ- proclitic mis-described as 'construct state'",
    },
    {
        "ref": "Mark 1:1",
        "chapter": 1, "verse": 1,
        # υἱοῦ ↔ ܒܪܗ group; Greek index ~5
        "greek_locator": [5],
        # error = calling it 'aligned'/'agreement' (missing the possessive suffix)
        "repeats_error": lambda g: g.get("variant") == "aligned" or _norm(g.get("type")) == "agreement",
        "desc": "Peshitta possessive suffix on ܒܪܗ ('his son') missed; verdict wrongly 'aligned'",
    },
    {
        "ref": "Mark 1:1",
        "chapter": 1, "verse": 1,
        # τοῦ θεοῦ group; Greek indices ~6-7
        "greek_locator": [6, 7],
        "repeats_error": lambda g: "omit the article" in _norm(g.get("note")) or "omits the article" in _norm(g.get("note")),
        "desc": "Syriac 'omits the article' mischaracterization (conflates grammar systems)",
    },
]


def load_verse(root: Path, chapter: int, verse: int) -> dict | None:
    p = root / "mark" / str(chapter) / f"{verse}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def best_group(verse_data: dict, greek_locator: list[int]) -> dict | None:
    """Return the alignment group whose Greek token set overlaps the locator most."""
    loc = set(greek_locator)
    best, best_overlap = None, -1
    for g in verse_data.get("alignment", []):
        overlap = len(set(g.get("greek_nt", [])) & loc)
        if overlap > best_overlap:
            best, best_overlap = g, overlap
    return best if best_overlap > 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    label = args.label or str(args.root)

    print(f"## Known-error check — {label}\n")
    print(f"Root: {args.root}\n")
    avoided = 0
    repeated = 0
    missing = 0
    rows = []
    for ke in KNOWN_ERRORS:
        vd = load_verse(args.root, ke["chapter"], ke["verse"])
        if vd is None:
            rows.append((ke["ref"], "VERSE MISSING", ke["desc"]))
            missing += 1
            continue
        g = best_group(vd, ke["greek_locator"])
        if g is None:
            rows.append((ke["ref"], "GROUP NOT FOUND", ke["desc"]))
            missing += 1
            continue
        if ke["repeats_error"](g):
            rows.append((ke["ref"], "REPEATS error", ke["desc"]))
            repeated += 1
        else:
            rows.append((ke["ref"], "AVOIDS error", ke["desc"]))
            avoided += 1

    for ref, status, desc in rows:
        mark = {"AVOIDS error": "✓", "REPEATS error": "✗"}.get(status, "?")
        print(f"  {mark} [{ref}] {status} — {desc}")
    total_checkable = avoided + repeated
    print()
    print(f"  Avoided: {avoided}/{total_checkable}   Repeated: {repeated}/{total_checkable}   "
          f"Unresolvable: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
