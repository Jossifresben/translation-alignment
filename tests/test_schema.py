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
    for group in valid_alignment["alignment"]:
        group.pop("vulgate", None)
    validate_alignment(valid_alignment)


def test_confidence_out_of_range_fails(valid_alignment):
    valid_alignment["meta"]["confidence"] = 1.5
    with pytest.raises(AlignmentValidationError, match="confidence"):
        validate_alignment(valid_alignment)
