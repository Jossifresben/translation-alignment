"""Run the Berean preflight benchmark.

For a random sample of Mark verses:
  1. Load the reference Greek↔English per-token alignment from Berean
     (derived from bsb_tables.tsv, saved as data/benchmarks/berean_mark_source.json).
  2. Ask Claude to independently align the same Greek tokens against the
     WEB English gloss we already ship.
  3. Compare: for each Greek token, check whether Claude's English target has
     any word-set overlap with Berean's English gloss (case-insensitive,
     bracket-stripped). Count matches.
  4. Write data/benchmarks/berean_preflight.json with headline agreement rate,
     sample size, model id, timestamp, and per-verse breakdown.

Berean is used ONLY as a methodology benchmark — never as display data.

Usage:
    python scripts/run_berean_benchmark.py \
        --berean data/benchmarks/berean_mark_source.json \
        --sample-size 20 \
        [--model claude-sonnet-4-5] \
        [--data-dir data] [--seed 42]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Override: some shells preset ANTHROPIC_API_KEY to an empty string, which
    # would otherwise block the value in .env from loading.
    load_dotenv(override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-5"

# A Berean English gloss may be just "-" or ". . ." when the token is purely
# grammatical (article, agreement particle) with no English counterpart.
# Treat these as non-scoring (we skip them from the denominator).
_SKIP_GLOSSES = {"-", ". . .", "...", "…"}


# ---------------------------------------------------------------------------
# Normalization + comparison helpers
# ---------------------------------------------------------------------------

_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_PUNCT_RE = re.compile(r"[^\w\s']", re.UNICODE)
# Greek punctuation that clings to words in our corpora: ·, ;, ,, ., ¶, ·, :
_GREEK_PUNCT_RE = re.compile(r"[·;,.¶:·\u0387\u037E\u00B7\u2029]", re.UNICODE)


def normalize_gloss(text: str) -> str:
    """Lowercase, strip [brackets] and surrounding whitespace.

    Brackets in Berean mark words the translators supplied that aren't in the
    Greek ("[the] Son"). For the overlap check we want to compare on the
    actual target words only.
    """
    if text is None:
        return ""
    cleaned = _BRACKET_RE.sub(" ", text)
    cleaned = cleaned.replace("-", " ")
    cleaned = cleaned.lower().strip()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _word_set(text: str) -> set[str]:
    """Tokenize normalized gloss into a set of content words."""
    norm = normalize_gloss(text)
    if not norm:
        return set()
    # Strip punctuation except apostrophes (keep "it's", "[the]'s" etc)
    norm = _PUNCT_RE.sub(" ", norm)
    words = [w for w in norm.split() if w]
    return set(words)


def normalize_greek(token: str) -> str:
    """Lowercase + strip surrounding punctuation from a Greek token.

    Used to pair tokens across sources whose surface forms differ only in
    capitalization or trailing punctuation. Diacritics are preserved: a
    breathing/accent mismatch between sources is rare enough to ignore for
    benchmarking, and collapsing them would hurt more than it helps.
    """
    if not token:
        return ""
    t = _GREEK_PUNCT_RE.sub("", token)
    return t.lower().strip()


def compute_agreement(
    berean: list[dict], claude: list[dict], greek_tokens: list[str] | None = None
) -> tuple[float, int, int]:
    """Return (rate, matched, total) comparing Claude vs Berean per Greek token.

    Berean's token order follows the English sentence flow, not the canonical
    Greek word order we ship in greek_nt.csv. So matching by greek_idx alone
    doesn't work. Instead:

      - If `greek_tokens` (the canonical Greek token list) is supplied, Claude's
        alignments are keyed by greek_idx into that list, and we pair Berean
        tokens to it by normalized Greek form, preserving order for duplicates
        (e.g. καὶ repeated in one verse).
      - If `greek_tokens` is not supplied (test paths), we fall back to the
        simple greek_idx-keyed comparison.

    A token matches when the two sides share at least one word after
    normalization. Tokens whose Berean gloss is purely grammatical ('-', '. . .')
    are excluded from the denominator.
    """
    claude_by_idx: dict[int, str] = {}
    for c in claude:
        try:
            idx = int(c.get("greek_idx"))
        except (TypeError, ValueError):
            continue
        claude_by_idx[idx] = c.get("english_target", "") or ""

    # Build a map from Berean's internal greek_idx -> our canonical idx.
    # For each Berean token, find the first unclaimed canonical token whose
    # normalized Greek form matches. If nothing matches, Berean's entry has no
    # canonical counterpart (text-critical difference) and we skip it.
    if greek_tokens is not None:
        canonical = [normalize_greek(t) for t in greek_tokens]
        claimed = [False] * len(canonical)
        berean_to_canon: dict[int, int] = {}
        for b in berean:
            b_greek_norm = normalize_greek(b.get("greek", ""))
            if not b_greek_norm:
                continue
            # First pass: look for an unclaimed exact match.
            found = -1
            for i, g in enumerate(canonical):
                if not claimed[i] and g == b_greek_norm:
                    found = i
                    break
            if found < 0:
                # Fallback: exact match even if claimed (duplicates where
                # counts differ between sources).
                for i, g in enumerate(canonical):
                    if g == b_greek_norm:
                        found = i
                        break
            if found >= 0:
                claimed[found] = True
                berean_to_canon[int(b["greek_idx"])] = found
    else:
        berean_to_canon = {}

    matched = 0
    total = 0
    for b in berean:
        try:
            b_idx = int(b.get("greek_idx"))
        except (TypeError, ValueError):
            continue
        b_eng = (b.get("english") or "").strip()
        if b_eng in _SKIP_GLOSSES or not b_eng:
            continue
        if greek_tokens is not None:
            canon_idx = berean_to_canon.get(b_idx)
            if canon_idx is None:
                # Berean has a token we don't ship (text-critical); skip.
                continue
            c_eng = claude_by_idx.get(canon_idx, "")
        else:
            c_eng = claude_by_idx.get(b_idx, "")
        total += 1
        b_words = _word_set(b_eng)
        c_words = _word_set(c_eng)
        if b_words and c_words and (b_words & c_words):
            matched += 1

    rate = (matched / total) if total else 0.0
    return rate, matched, total


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_corpus(path: Path) -> dict[str, str]:
    """Return {reference: text} from a corpora CSV."""
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            result[row["reference"]] = row["text"]
    return result


def load_berean(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are aligning a Greek New Testament verse against its \
English translation, token-by-token.

You will receive:
- The Greek tokens of one verse (as a JSON list, with indexes)
- The full English translation of that verse (a single sentence/paragraph)

Your job: for every Greek token, identify the English word or words in the \
translation that correspond to that token. Some Greek tokens (articles, \
particles, agreement markers) will have no distinct English counterpart — \
for those, return an empty string.

Return ONLY a JSON object of the form:
{"alignment": [{"greek_idx": 0, "english_target": "beginning"},
               {"greek_idx": 1, "english_target": "of the"},
               ...]}

Rules:
- One entry per Greek token, in index order.
- english_target MUST be words drawn from the provided English translation, \
not paraphrases.
- If a Greek token has no English counterpart, return "".
- No markdown, no prose outside the JSON.
"""


def build_user_msg(
    ref: str, greek_tokens: list[str], english_text: str
) -> str:
    indexed = [{"greek_idx": i, "greek": t} for i, t in enumerate(greek_tokens)]
    payload = {
        "reference": ref,
        "greek_tokens": indexed,
        "english_translation": english_text,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json\n"):
            text = text[5:]
        elif text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def call_claude(client, model: str, ref: str, greek_tokens: list[str],
                english_text: str) -> list[dict]:
    user_msg = build_user_msg(ref, greek_tokens, english_text)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.0,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT,
             "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    text = response.content[0].text
    data = _extract_json(text)
    alignment = data.get("alignment", [])
    if not isinstance(alignment, list):
        raise ValueError(f"alignment not a list for {ref}: {alignment!r}")
    return alignment


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    berean_path: Path,
    sample_size: int,
    model: str,
    data_dir: Path,
    seed: int,
) -> dict:
    berean_data = load_berean(berean_path)
    greek_map = load_corpus(data_dir / "corpora" / "greek_nt.csv")
    web_map = load_corpus(data_dir / "corpora" / "web.csv")

    refs = sorted(berean_data.keys())
    rng = random.Random(seed)
    n = min(sample_size, len(refs))
    sample = sorted(rng.sample(refs, n))

    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    per_verse: list[dict] = []
    total_matched = 0
    total_tokens = 0
    run_started = datetime.now(timezone.utc)

    for i, ref in enumerate(sample, 1):
        greek_text = greek_map.get(ref, "")
        english_text = web_map.get(ref, "")
        if not greek_text or not english_text:
            logger.warning("Skipping %s: missing greek or english text", ref)
            continue
        greek_tokens = greek_text.split()
        berean_tokens = berean_data[ref]

        logger.info("[%d/%d] %s — %d Greek tokens (Berean: %d)",
                    i, n, ref, len(greek_tokens), len(berean_tokens))
        try:
            claude_align = call_claude(client, model, ref, greek_tokens,
                                       english_text)
        except Exception as e:
            logger.exception("Claude call failed for %s: %s", ref, e)
            claude_align = []

        rate, matched, total = compute_agreement(
            berean_tokens, claude_align, greek_tokens=greek_tokens
        )
        logger.info("    matched %d/%d = %.1f%%", matched, total, rate * 100)
        per_verse.append({
            "ref": ref,
            "rate": round(rate, 4),
            "matched": matched,
            "total": total,
        })
        total_matched += matched
        total_tokens += total

    headline_rate = (total_matched / total_tokens) if total_tokens else 0.0
    return {
        "agreement_rate": round(headline_rate, 4),
        "matched_tokens": total_matched,
        "total_tokens": total_tokens,
        "sample_size": len(per_verse),
        "seed": seed,
        "model": model,
        "run_at": run_started.isoformat(),
        "per_verse": per_verse,
        "methodology": (
            "Claude aligns Greek tokens to English words; compared against "
            "Berean Interlinear word-level alignment. Agreement = any word "
            "overlap (case-insensitive, bracket-stripped) between Claude's "
            "target and Berean's gloss for each Greek token. Greek tokens "
            "whose Berean gloss is purely grammatical ('-', '. . .') are "
            "excluded from the denominator."
        ),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--berean", type=Path,
                    default=Path("data/benchmarks/berean_mark_source.json"))
    ap.add_argument("--sample-size", type=int, default=20)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path,
                    default=Path("data/benchmarks/berean_preflight.json"))
    args = ap.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ or not os.environ["ANTHROPIC_API_KEY"]:
        print("ERROR: ANTHROPIC_API_KEY is not set (check .env)", file=sys.stderr)
        sys.exit(2)

    result = run_benchmark(
        berean_path=args.berean,
        sample_size=args.sample_size,
        model=args.model,
        data_dir=args.data_dir,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote %s", args.out)
    logger.info(
        "Headline agreement: %.1f%% (%d / %d tokens across %d verses)",
        result["agreement_rate"] * 100,
        result["matched_tokens"], result["total_tokens"], result["sample_size"],
    )


if __name__ == "__main__":
    main()
