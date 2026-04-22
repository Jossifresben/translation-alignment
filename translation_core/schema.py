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
