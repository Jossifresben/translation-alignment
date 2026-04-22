"""Test alignment → HTML rendering."""
import json
from pathlib import Path

import pytest

from translation_core.rendering import token_variant_map, render_tokens_html


@pytest.fixture
def fixture_data() -> dict:
    p = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    return json.loads(p.read_text(encoding="utf-8"))


def test_token_variant_map_assigns_minor_to_right_tokens(fixture_data):
    m = token_variant_map(fixture_data, "greek_nt")
    assert m[5] == "minor"
    assert m[6] == "minor"
    assert m[0] == "aligned"


def test_render_tokens_html_wraps_with_variant_classes(fixture_data):
    html = render_tokens_html(fixture_data, "greek_nt")
    assert '<span class="tok aligned"' in html
    assert '<span class="tok minor"' in html
    assert html.count(">Ἀρχὴ<") == 1
    # STEP tokenization includes trailing punctuation on the final token.
    assert html.count(">θεοῦ·<") == 1


def test_render_tokens_html_adds_aria_label_for_non_aligned(fixture_data):
    html = render_tokens_html(fixture_data, "greek_nt")
    assert 'aria-label="θεοῦ — minor variant"' in html or 'aria-label="υἱοῦ — minor variant"' in html


def test_render_tokens_html_handles_absent_tradition():
    data = {
        "ref": "Mark 99:99",
        "chapter": 99, "verse": 99,
        "traditions": {"vulgate": {"absent": True}},
        "alignment": [],
        "meta": {"generated_by": "test", "generated_at": "2026-04-22",
                 "confidence": 1.0, "schema_version": 1},
    }
    html = render_tokens_html(data, "vulgate")
    assert "absent" in html.lower()
