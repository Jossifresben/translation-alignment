"""Test the generate_alignments script's pure helpers."""
import json
from pathlib import Path

import pytest

from scripts.generate_alignments import (
    build_user_message,
    validate_and_normalize_response,
    PILOT_VERSES,
)


def test_pilot_contains_10_verses():
    assert len(PILOT_VERSES) == 10
    assert ("Mark", 1, 1) in PILOT_VERSES


def test_build_user_message_includes_all_three_traditions():
    msg = build_user_message(
        greek_tokens=["a", "b"],
        peshitta_tokens=["x"],
        vulgate_tokens=["y"],
        enrichment={"greek_strong": [], "peshitta_roots": []},
    )
    assert '"greek_tokens"' in msg
    assert '"peshitta_tokens"' in msg
    assert '"vulgate_tokens"' in msg


def test_validate_and_normalize_accepts_valid_response():
    raw = {
        "alignment": [
            {"greek_nt": [0, 1], "peshitta": [0], "vulgate": [0], "variant": "aligned"}
        ],
        "confidence": 0.9,
    }
    traditions = {
        "greek_nt": {"tokens": ["a", "b"]},
        "peshitta": {"tokens": ["x"]},
        "vulgate":  {"tokens": ["y"]},
    }
    result = validate_and_normalize_response(raw, traditions, ref="Mark 1:1",
                                             chapter=1, verse=1,
                                             model="claude-sonnet-4-5")
    assert result["ref"] == "Mark 1:1"
    assert result["meta"]["confidence"] == 0.9
    assert result["meta"]["generated_by"] == "claude-sonnet-4-5"


def test_validate_and_normalize_rejects_missing_alignment_key():
    with pytest.raises(Exception):
        validate_and_normalize_response({"confidence": 0.9}, traditions={}, ref="x",
                                        chapter=1, verse=1, model="x")
