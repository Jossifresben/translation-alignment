"""Tests for scripts.run_berean_benchmark — normalize + compare helpers."""
from scripts.run_berean_benchmark import normalize_gloss, compute_agreement


def test_normalize_gloss_strips_brackets_and_lowercases():
    assert normalize_gloss("[The] beginning") == "beginning"
    assert normalize_gloss("  God  ") == "god"
    assert normalize_gloss("of the") == "of the"


def test_compute_agreement_all_match():
    b = [{"greek_idx": 0, "english": "beginning"},
         {"greek_idx": 1, "english": "gospel"}]
    c = [{"greek_idx": 0, "english_target": "beginning"},
         {"greek_idx": 1, "english_target": "gospel"}]
    rate, matched, total = compute_agreement(b, c)
    assert rate == 1.0 and matched == 2 and total == 2


def test_compute_agreement_partial_overlap():
    b = [{"greek_idx": 0, "english": "the beginning"}]
    c = [{"greek_idx": 0, "english_target": "beginning"}]
    rate, matched, total = compute_agreement(b, c)
    # Word-set overlap => match
    assert matched == 1


def test_compute_agreement_zero_when_no_claude_result():
    b = [{"greek_idx": 0, "english": "beginning"}]
    c = []
    rate, matched, total = compute_agreement(b, c)
    assert matched == 0 and total == 1 and rate == 0.0


def test_compute_agreement_skips_grammatical_glosses():
    # Berean's '-' and '. . .' entries have no English counterpart —
    # they should not count toward the denominator at all.
    b = [{"greek_idx": 0, "english": "beginning"},
         {"greek_idx": 1, "english": "-"},
         {"greek_idx": 2, "english": ". . ."}]
    c = [{"greek_idx": 0, "english_target": "beginning"}]
    rate, matched, total = compute_agreement(b, c)
    assert total == 1 and matched == 1 and rate == 1.0


def test_normalize_gloss_handles_case_and_trailing_bracket_word():
    # "[the] Son" should reduce to "son" (bracketed translator word dropped)
    assert normalize_gloss("[the] Son") == "son"
    assert normalize_gloss("[This is the] beginning") == "beginning"


def test_compute_agreement_with_reordered_greek_pairs_by_form():
    # Berean's token order follows English flow; canonical is Greek order.
    # greek_tokens = our canonical order.
    greek_tokens = ["αὐτὸς", "οὖν", "Δαυὶδ", "λέγει"]
    # Berean reordered: David first, then himself, then calls.
    b = [
        {"greek_idx": 0, "greek": "Δαυὶδ", "english": "David"},
        {"greek_idx": 1, "greek": "Αὐτὸς", "english": "himself"},
        {"greek_idx": 2, "greek": "λέγει", "english": "calls"},
    ]
    # Claude aligned against canonical Greek order (0=αὐτὸς, 2=Δαυὶδ, 3=λέγει).
    c = [
        {"greek_idx": 0, "english_target": "himself"},
        {"greek_idx": 1, "english_target": ""},
        {"greek_idx": 2, "english_target": "David"},
        {"greek_idx": 3, "english_target": "calls"},
    ]
    rate, matched, total = compute_agreement(b, c, greek_tokens=greek_tokens)
    assert total == 3 and matched == 3 and rate == 1.0


def test_compute_agreement_skips_berean_only_tokens():
    # Berean has a token our canonical Greek doesn't include (e.g. text-critical
    # variant). That token should be excluded from the denominator.
    greek_tokens = ["Ἀρχὴ", "τοῦ", "εὐαγγελίου"]
    b = [
        {"greek_idx": 0, "greek": "Ἀρχὴ", "english": "beginning"},
        {"greek_idx": 1, "greek": "τοῦ", "english": "of the"},
        {"greek_idx": 2, "greek": "εὐαγγελίου", "english": "gospel"},
        # A token that's not in the canonical list:
        {"greek_idx": 3, "greek": "NOTREAL", "english": "extra"},
    ]
    c = [
        {"greek_idx": 0, "english_target": "beginning"},
        {"greek_idx": 1, "english_target": "of the"},
        {"greek_idx": 2, "english_target": "gospel"},
    ]
    rate, matched, total = compute_agreement(b, c, greek_tokens=greek_tokens)
    assert total == 3 and matched == 3
