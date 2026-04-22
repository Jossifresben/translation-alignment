"""Convert our alignment JSON shape into the designer's verse/witness/variants shape.

Our shape (input):
    { ref, chapter, verse, traditions: {id: {tokens: [...]}}, alignment: [groups], meta }

Designer shape (output):
    { book, chapter, verse, ref, prev, next, pericope, testament, gloss_en,
      witnesses: [{id, sigil, name, subtitle, script, date, dir, tokens}],
      variants: [{id, type, label, title, gloss, witnesses, summary, classes}] }

Each output token: {t, a?, v?, gloss?, punct?, idx?}
"""
from __future__ import annotations

import json
from pathlib import Path

# Fixed witness metadata per tradition (MVP — Mark only)
WITNESS_META = {
    "greek_nt": {
        "id": "grk", "sigil": "𝔊", "name": "Greek NT",
        "subtitle": "STEP TAGNT (NA28/Byzantine amalgamated)", "script": "grc",
        "date": "c. 70–90 CE", "dir": "ltr",
    },
    "peshitta": {
        "id": "syr", "sigil": "ℙ", "name": "Peshitta",
        "subtitle": "Syriac, 5th c.", "script": "syr",
        "date": "c. 400 CE", "dir": "rtl",
    },
    "vulgate": {
        "id": "vul", "sigil": "𝔙", "name": "Vulgate",
        "subtitle": "Clementine, Jerome", "script": "lat",
        "date": "c. 400 CE", "dir": "ltr",
    },
}

# Map our runtime tradition id → designer witness id
TRAD_TO_WITNESS = {"greek_nt": "grk", "peshitta": "syr", "vulgate": "vul"}

# Default variant titles when we have to synthesize one
VARIANT_TITLE_TEMPLATE = {
    "minor": "Minor divergence",
    "major": "Major divergence",
    "omitted": "Omission",
    "added": "Addition",
}

VARIANT_CLASS_FROM_VERDICT = {
    "minor": "minor", "major": "major",
    "omitted": "major", "added": "major",
}

# Map our group `type` enum (if present) → designer's variant `type`
TYPE_MAP = {
    "agreement": "agreement", "expansion": "expansion", "omission": "omission",
    "substitution": "substitution", "harmonisation": "harmonisation",
    "word-order": "construction", "construction": "construction",
    "idiom": "idiom", "punctuation": "punctuation",
    "grammar": "grammar", "lexical": "lexical", "gloss": "gloss",
}


def _normalize_pericope_lookup(pericopes: dict, book: str, chapter: int, verse: int) -> str | None:
    entries = pericopes.get(book, [])
    for entry in entries:
        (c1, v1), (c2, v2) = entry["range"]
        if (chapter, verse) < (c1, v1):
            continue
        if (chapter, verse) > (c2, v2):
            continue
        return entry["title"]
    return None


def _split_punctuation(token: str) -> list[dict]:
    """Split a whitespace-separated token into {t, punct?} pieces.

    Accepts tokens like 'θεοῦ.' and emits [{t:'θεοῦ'},{t:'.',punct:True}].
    Accepts tokens like ',' and emits [{t:',',punct:True}].
    Keeps Syriac/Greek diacritics intact.
    """
    # Trailing punctuation set — conservative: western punctuation + Greek middot
    punct_chars = set(",.;:·?!·—–")
    pieces: list[dict] = []
    core = token
    trailing: list[str] = []
    while core and core[-1] in punct_chars:
        trailing.append(core[-1])
        core = core[:-1]
    leading: list[str] = []
    while core and core[0] in punct_chars:
        leading.append(core[0])
        core = core[1:]
    for p in leading:
        pieces.append({"t": p, "punct": True})
    if core:
        pieces.append({"t": core})
    for p in reversed(trailing):
        pieces.append({"t": p, "punct": True})
    return pieces


def _token_index_map(trad_data: dict, raw_tokens: list[str]) -> list[tuple[dict, int | None]]:
    """Build a flat list of output-token dicts (with optional source idx) from raw tokens.

    Returns list of (out_token_dict, source_idx_or_None). Source idx points back
    to the position in the ORIGINAL `tokens` list for enrichment lookup; None for
    punctuation pieces we split off.
    """
    result: list[tuple[dict, int | None]] = []
    for i, tok in enumerate(raw_tokens):
        pieces = _split_punctuation(tok)
        for piece in pieces:
            if piece.get("punct"):
                result.append((piece, None))
            else:
                # Carry idx on the "real" piece for enrichment lookup
                piece["idx"] = i
                result.append((piece, i))
    return result


def _build_witness_tokens(
    trad_id: str,
    trad_data: dict,
    group_by_src_idx: dict[int, dict],
    per_token_glosses: dict[int, str] | None = None,
) -> list[dict]:
    """Build the witness's token list, assigning `a` (align) and `v` (variant) ids
    to each non-punctuation token based on which alignment group contains its idx.
    """
    if trad_data.get("absent"):
        return []
    raw_tokens = trad_data.get("tokens", [])
    flat = _token_index_map(trad_data, raw_tokens)
    out: list[dict] = []
    for piece, src_idx in flat:
        if piece.get("punct"):
            piece["a"] = None
            out.append(piece)
            continue
        group = group_by_src_idx.get(src_idx) if src_idx is not None else None
        if group is not None:
            piece["a"] = group["_align_id"]
            if group.get("variant") != "aligned":
                piece["v"] = group["_variant_id"]
                piece["variant_type"] = group.get("variant")  # minor / major / omitted / added
        else:
            piece["a"] = None
        if per_token_glosses and src_idx is not None and src_idx in per_token_glosses:
            piece["gloss"] = per_token_glosses[src_idx]
        out.append(piece)
    return out


def _synthesize_title(group: dict, witnesses: list[dict]) -> str:
    """Produce a short scholarly title from the tokens in the group."""
    parts: list[str] = []
    for w in witnesses:
        trad_id = next(k for k, v in TRAD_TO_WITNESS.items() if v == w["id"])
        indices = group.get(trad_id, [])
        if not indices:
            continue
        source_tokens = _source_tokens_for_witness(w)
        picked = " ".join(source_tokens[i] for i in indices if i < len(source_tokens))
        if picked:
            parts.append(f"{w['name']}: {picked}")
    return " · ".join(parts) if parts else "Divergence"


def _source_tokens_for_witness(w: dict) -> list[str]:
    """Flatten the witness's output tokens back to their surface strings (best-effort)."""
    toks: list[str] = []
    for t in w.get("tokens", []):
        if not t.get("punct"):
            toks.append(t.get("t", ""))
    return toks


def convert_alignment_to_verse(
    alignment: dict,
    *,
    book: str,
    book_lower: str,
    prev_cv: tuple[int, int] | None,
    next_cv: tuple[int, int] | None,
    pericopes: dict,
    testament: str,
    gloss_en: str | None,
    greek_glosses: dict[int, str] | None = None,
) -> dict:
    """Return a designer-shape verse dict from our alignment JSON."""
    chapter = alignment["chapter"]
    verse = alignment["verse"]
    ref = alignment["ref"]
    groups = alignment["alignment"]

    # 1) Assign stable align ids + variant ids to each group
    group_by_src_idx_per_trad: dict[str, dict[int, dict]] = {
        trad_id: {} for trad_id in alignment["traditions"]
    }
    variants_out: list[dict] = []
    for gi, group in enumerate(groups, start=1):
        group["_align_id"] = f"g{gi}"
        if group.get("variant") != "aligned":
            group["_variant_id"] = f"v{gi}"
        for trad_id in alignment["traditions"]:
            for idx in group.get(trad_id, []):
                group_by_src_idx_per_trad[trad_id][idx] = group

    # 2) Build witnesses
    witnesses: list[dict] = []
    for trad_id in ("greek_nt", "peshitta", "vulgate"):
        trad = alignment["traditions"].get(trad_id)
        if not trad:
            continue
        meta = WITNESS_META[trad_id]
        glosses = greek_glosses if trad_id == "greek_nt" else None
        witnesses.append({
            **meta,
            "tokens": _build_witness_tokens(
                trad_id, trad, group_by_src_idx_per_trad[trad_id], per_token_glosses=glosses
            ),
        })

    # 3) Build variants list — one entry per non-aligned group
    for group in groups:
        if group.get("variant") == "aligned":
            continue
        vid = group["_variant_id"]
        verdict = group.get("variant", "minor")
        type_slug = TYPE_MAP.get(group.get("type") or "", None)
        if not type_slug:
            type_slug = "expansion" if verdict == "added" else (
                "omission" if verdict == "omitted" else (
                "substitution" if verdict == "major" else "construction"))
        attest_ids: list[str] = []
        for trad_id in ("greek_nt", "peshitta", "vulgate"):
            if group.get(trad_id):
                attest_ids.append(TRAD_TO_WITNESS[trad_id])
        label = "All three attest" if len(attest_ids) == 3 else (
            "Two witnesses" if len(attest_ids) == 2 else
            f"{witnesses[0]['name'] if attest_ids else ''} only"
            if len(attest_ids) == 1 else "—"
        )
        if len(attest_ids) == 1:
            name_map = {w["id"]: w["name"] for w in witnesses}
            label = f"{name_map.get(attest_ids[0], attest_ids[0])} only"
        title = _synthesize_title(group, witnesses)
        summary = group.get("note") or title
        variants_out.append({
            "id": vid,
            "type": type_slug,
            "label": label,
            "title": title,
            "gloss": None,
            "witnesses": attest_ids,
            "summary": summary,
            "classes": [VARIANT_CLASS_FROM_VERDICT.get(verdict, "minor"), type_slug],
        })

    # 4) Top-level fields
    prev = None
    if prev_cv:
        pc, pv = prev_cv
        prev = {"label": f"{book} {pc}:{pv}", "book": book_lower, "chapter": pc, "verse": pv}
    nxt = None
    if next_cv:
        nc, nv = next_cv
        nxt = {"label": f"{book} {nc}:{nv}", "book": book_lower, "chapter": nc, "verse": nv}

    return {
        "book": book,
        "chapter": chapter,
        "verse": verse,
        "ref": ref,
        "prev": prev,
        "next": nxt,
        "pericope": _normalize_pericope_lookup(pericopes, book, chapter, verse),
        "testament": testament,
        "gloss_en": gloss_en,
        "witnesses": witnesses,
        "variants": variants_out,
    }
