"""Generate 3-way alignments for Mark via Claude.

Modes:
    --pilot             Generate the 10-verse calibration sample (sync API)
    --verse Mark 1 1    Generate a single specific verse (sync API)
    --full              Generate all remaining Mark verses via the Batch API
    --report            Summarize low-confidence and quarantined verses

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Override: some shells preset ANTHROPIC_API_KEY to an empty string, which
    # would otherwise block the value in .env from loading.
    load_dotenv(override=True)
except ImportError:
    pass

from translation_core.schema import validate_alignment, AlignmentValidationError
from translation_core.corpora import CorpusRegistry

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-5"

PILOT_VERSES: list[tuple[str, int, int]] = [
    ("Mark", 1, 1),
    ("Mark", 1, 15),
    ("Mark", 3, 27),
    ("Mark", 5, 41),
    ("Mark", 8, 29),
    ("Mark", 10, 45),
    ("Mark", 13, 14),
    ("Mark", 14, 36),
    ("Mark", 15, 34),
    ("Mark", 16, 8),
]

PROMPT_DIR = Path(__file__).parent / "prompts"
FEW_SHOT_FIXTURE = Path("tests/fixtures/few_shot_examples.json")


def load_system_prompt() -> str:
    return (PROMPT_DIR / "align_3way.md").read_text(encoding="utf-8")


def load_few_shot_examples() -> list[dict]:
    if not FEW_SHOT_FIXTURE.exists():
        return []
    return list(json.loads(FEW_SHOT_FIXTURE.read_text(encoding="utf-8")).values())


def build_user_message(
    greek_tokens: list[str],
    peshitta_tokens: list[str],
    vulgate_tokens: list[str],
    enrichment: dict,
) -> str:
    payload = {
        "greek_tokens": greek_tokens,
        "peshitta_tokens": peshitta_tokens,
        "vulgate_tokens": vulgate_tokens,
        "enrichment": enrichment,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from a model response that may be fenced or prefixed."""
    text = text.strip()
    if text.startswith("```"):
        # Strip code fence
        text = text.strip("`")
        if text.startswith("json\n"):
            text = text[5:]
        elif text.startswith("json"):
            text = text[4:]
    # If the model still added prose before/after, try to locate the outermost {...}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def call_claude_sync(
    client,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
    user_msg: str,
    retry_on_bad_json: bool = True,
) -> dict:
    messages: list[dict] = []
    for ex in few_shot:
        messages.append({"role": "user",
                         "content": json.dumps(ex["input"], ensure_ascii=False)})
        messages.append({"role": "assistant",
                         "content": json.dumps(ex["output"], ensure_ascii=False)})
    messages.append({"role": "user", "content": user_msg})

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        temperature=0.1,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    text = response.content[0].text
    try:
        return _extract_json(text)
    except json.JSONDecodeError:
        if not retry_on_bad_json:
            raise
        logger.warning("First call returned non-JSON; retrying with stricter instruction.")
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user",
                         "content": "Return ONLY a raw JSON object — no markdown, no prose."})
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.1,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )
        return _extract_json(response.content[0].text)


def validate_and_normalize_response(
    raw: dict,
    traditions: dict,
    ref: str,
    chapter: int,
    verse: int,
    model: str,
) -> dict:
    if "alignment" not in raw:
        raise ValueError(f"Response missing 'alignment' key: {raw!r}")
    confidence = raw.get("confidence", 0.5)
    data = {
        "ref": ref,
        "chapter": chapter,
        "verse": verse,
        "traditions": traditions,
        "alignment": raw["alignment"],
        "meta": {
            "generated_by": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "confidence": float(confidence),
            "schema_version": 1,
        },
    }
    validate_alignment(data)
    return data


def generate_one_verse(
    client,
    corpora: CorpusRegistry,
    greek_enrich: dict,
    peshitta_enrich: dict,
    book: str,
    chapter: int,
    verse: int,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
) -> dict:
    greek = corpora.get("greek_nt").get(book, chapter, verse) or ""
    peshitta = corpora.get("peshitta").get(book, chapter, verse) or ""
    vulgate = ""
    try:
        vulgate = corpora.get("vulgate").get(book, chapter, verse) or ""
    except KeyError:
        pass

    greek_tokens = greek.split()
    peshitta_tokens = peshitta.split()
    vulgate_tokens = vulgate.split()

    ref = f"{book} {chapter}:{verse}"
    # Clip enrichment to the corpus token range so the model never sees
    # enrichment pointing at indices beyond the provided token list.
    greek_strong = [
        e for e in greek_enrich.get(ref, [])
        if isinstance(e, dict) and e.get("token_idx", -1) < len(greek_tokens)
    ]
    peshitta_roots = [
        e for e in peshitta_enrich.get(ref, [])
        if isinstance(e, dict) and e.get("token_idx", -1) < len(peshitta_tokens)
    ]
    enrichment = {
        "greek_strong": greek_strong,
        "peshitta_roots": peshitta_roots,
    }
    user_msg = build_user_message(greek_tokens, peshitta_tokens, vulgate_tokens, enrichment)

    raw = call_claude_sync(client, model, system_prompt, few_shot, user_msg)

    traditions = {
        "greek_nt": {"tokens": greek_tokens} if greek_tokens else {"absent": True},
        "peshitta": {"tokens": peshitta_tokens} if peshitta_tokens else {"absent": True},
        "vulgate":  {"tokens": vulgate_tokens} if vulgate_tokens else {"absent": True},
    }
    return validate_and_normalize_response(raw, traditions, ref, chapter, verse, model)


def save_alignment(data: dict, out_root: Path) -> Path:
    ch = data["chapter"]
    v = data["verse"]
    out = out_root / "mark" / str(ch) / f"{v}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_pilot(client, corpora, greek_enrich, peshitta_enrich, out_root: Path,
              model: str, system_prompt: str, few_shot: list[dict]) -> dict:
    stats = {"verses": [], "started_at": time.time()}
    for book, ch, v in PILOT_VERSES:
        t0 = time.time()
        try:
            data = generate_one_verse(client, corpora, greek_enrich, peshitta_enrich,
                                      book, ch, v, model, system_prompt, few_shot)
            save_alignment(data, out_root)
            ok, err, conf = True, None, data["meta"]["confidence"]
        except Exception as e:
            ok, err, conf = False, str(e), None
        dur = time.time() - t0
        stats["verses"].append({"ref": f"{book} {ch}:{v}", "ok": ok,
                                "duration_s": round(dur, 2),
                                "confidence": conf, "error": err})
        logger.info("  %s  %.2fs  %s  conf=%s",
                    f"{book} {ch}:{v}", dur, "ok" if ok else f"FAIL: {err}",
                    conf if conf is not None else "-")
    stats["elapsed_s"] = round(time.time() - stats["started_at"], 2)
    return stats


def _load_all(data_dir: Path):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    corpora = CorpusRegistry()
    corpora.add("greek_nt", "Greek NT", data_dir / "corpora" / "greek_nt.csv")
    corpora.add("peshitta", "Peshitta", data_dir / "corpora" / "peshitta_nt.csv")
    vulgate_path = data_dir / "corpora" / "vulgate.csv"
    if vulgate_path.exists():
        corpora.add("vulgate", "Vulgate", vulgate_path)
    greek_enrich_path = data_dir / "enrichment" / "greek_strong.json"
    greek_enrich = json.loads(greek_enrich_path.read_text(encoding="utf-8")) if greek_enrich_path.exists() else {}
    peshitta_enrich_path = data_dir / "enrichment" / "peshitta_roots.json"
    peshitta_enrich = json.loads(peshitta_enrich_path.read_text(encoding="utf-8")) if peshitta_enrich_path.exists() else {}
    return client, corpora, greek_enrich, peshitta_enrich


def build_batch_requests(
    corpora: CorpusRegistry,
    greek_enrich: dict,
    peshitta_enrich: dict,
    out_root: Path,
    model: str,
    system_prompt: str,
    few_shot: list[dict],
    force: bool = False,
) -> list[dict]:
    """One request per Mark verse that lacks a valid JSON (unless force=True)."""
    requests = []
    master = corpora.get("greek_nt")
    for ch in range(1, 17):
        for v in master.verses_in_chapter("Mark", ch):
            target = out_root / "mark" / str(ch) / f"{v}.json"
            if target.exists() and not force:
                continue
            greek = master.get("Mark", ch, v) or ""
            peshitta = ""
            try:
                peshitta = corpora.get("peshitta").get("Mark", ch, v) or ""
            except KeyError:
                pass
            vulgate = ""
            try:
                vulgate = corpora.get("vulgate").get("Mark", ch, v) or ""
            except KeyError:
                pass
            ref = f"Mark {ch}:{v}"
            greek_tokens = greek.split()
            peshitta_tokens = peshitta.split()
            vulgate_tokens = vulgate.split()
            # Clip enrichment to the corpus token range so the model never sees
            # enrichment pointing at indices beyond the provided token list.
            greek_strong = [
                e for e in greek_enrich.get(ref, [])
                if isinstance(e, dict) and e.get("token_idx", -1) < len(greek_tokens)
            ]
            peshitta_roots = [
                e for e in peshitta_enrich.get(ref, [])
                if isinstance(e, dict) and e.get("token_idx", -1) < len(peshitta_tokens)
            ]
            enrichment = {
                "greek_strong": greek_strong,
                "peshitta_roots": peshitta_roots,
            }
            user_msg = build_user_message(
                greek_tokens, peshitta_tokens, vulgate_tokens, enrichment
            )
            messages = []
            for ex in few_shot:
                messages.append({"role": "user",
                                 "content": json.dumps(ex["input"], ensure_ascii=False)})
                messages.append({"role": "assistant",
                                 "content": json.dumps(ex["output"], ensure_ascii=False)})
            messages.append({"role": "user", "content": user_msg})
            requests.append({
                "custom_id": f"mark_{ch}_{v}",
                "params": {
                    "model": model,
                    "max_tokens": 4000,
                    "temperature": 0.1,
                    "system": [
                        {"type": "text", "text": system_prompt,
                         "cache_control": {"type": "ephemeral"}}
                    ],
                    "messages": messages,
                },
            })
    return requests


def submit_batch_and_wait(client, requests: list[dict], poll_interval: int = 30) -> dict:
    """Submit a messages batch, poll until done, return {custom_id: response_dict_or_error}."""
    # The SDK's request type name varies across versions; use dicts directly.
    batch = client.messages.batches.create(requests=requests)
    logger.info("Submitted batch %s with %d requests", batch.id, len(requests))

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        counts = batch.request_counts
        logger.info("  batch %s status=%s succeeded=%d errored=%d processing=%d",
                    batch.id, batch.processing_status,
                    counts.succeeded, counts.errored, counts.processing)
        time.sleep(poll_interval)

    results: dict[str, dict] = {}
    for result in client.messages.batches.results(batch.id):
        cid = result.custom_id
        rtype = result.result.type
        if rtype == "succeeded":
            text = result.result.message.content[0].text
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json\n"):
                    text = text[5:]
            try:
                results[cid] = json.loads(text)
            except Exception as e:
                logger.error("  %s: JSON parse failed: %s", cid, e)
                results[cid] = {"_error": f"json_parse: {e}", "_raw": text[:500]}
        else:
            err = getattr(result.result, "error", None) or rtype
            logger.error("  %s: %s", cid, err)
            results[cid] = {"_error": str(err)}
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="Run the 10-verse pilot")
    ap.add_argument("--verse", nargs=3, metavar=("BOOK", "CH", "V"),
                    help="Generate a single verse")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--full", action="store_true",
                    help="Generate all remaining Mark verses via Batch API")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if a verse JSON already exists")
    ap.add_argument("--report", action="store_true",
                    help="Report low-confidence and quarantined verses")
    ap.add_argument("--threshold", type=float, default=0.7)
    args = ap.parse_args()

    client, corpora, greek_enrich, peshitta_enrich = _load_all(args.data_dir)
    system_prompt = load_system_prompt()
    few_shot = load_few_shot_examples()
    out_root = args.data_dir / "alignments"

    if args.pilot:
        stats = run_pilot(client, corpora, greek_enrich, peshitta_enrich,
                          out_root, args.model, system_prompt, few_shot)
        (out_root / "_pilot_stats.json").write_text(
            json.dumps(stats, indent=2), encoding="utf-8"
        )
        logger.info("Pilot complete. Stats saved to %s/_pilot_stats.json", out_root)
    elif args.verse:
        book, ch, v = args.verse[0], int(args.verse[1]), int(args.verse[2])
        data = generate_one_verse(client, corpora, greek_enrich, peshitta_enrich,
                                   book, ch, v, args.model, system_prompt, few_shot)
        path = save_alignment(data, out_root)
        logger.info("Wrote %s", path)
    elif args.full:
        requests = build_batch_requests(corpora, greek_enrich, peshitta_enrich,
                                         out_root, args.model, system_prompt,
                                         few_shot, force=args.force)
        if not requests:
            logger.info("No verses to generate. Use --force to regenerate existing.")
            return
        logger.info("Submitting batch with %d verse requests", len(requests))
        results = submit_batch_and_wait(client, requests)

        ok = 0
        fail = 0
        quarantine = out_root / "_quarantine"
        for cid, raw in results.items():
            _prefix, ch_str, v_str = cid.split("_")
            ch, v = int(ch_str), int(v_str)
            greek = corpora.get("greek_nt").get("Mark", ch, v) or ""
            peshitta = ""
            try:
                peshitta = corpora.get("peshitta").get("Mark", ch, v) or ""
            except KeyError:
                pass
            vulgate = ""
            try:
                vulgate = corpora.get("vulgate").get("Mark", ch, v) or ""
            except KeyError:
                pass
            traditions = {
                "greek_nt": {"tokens": greek.split()} if greek else {"absent": True},
                "peshitta": {"tokens": peshitta.split()} if peshitta else {"absent": True},
                "vulgate":  {"tokens": vulgate.split()} if vulgate else {"absent": True},
            }
            if "_error" in raw:
                quarantine.mkdir(parents=True, exist_ok=True)
                (quarantine / f"{cid}.json").write_text(
                    json.dumps(raw, indent=2), encoding="utf-8"
                )
                fail += 1
                continue
            try:
                data = validate_and_normalize_response(
                    raw, traditions, f"Mark {ch}:{v}", ch, v, args.model
                )
                save_alignment(data, out_root)
                ok += 1
            except AlignmentValidationError as e:
                quarantine.mkdir(parents=True, exist_ok=True)
                (quarantine / f"{cid}.json").write_text(
                    json.dumps({"_error": str(e), "raw": raw}, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                fail += 1
        logger.info("Full run done. succeeded=%d quarantined=%d", ok, fail)
    elif args.report:
        low_conf = []
        for ch in range(1, 17):
            ch_dir = out_root / "mark" / str(ch)
            if not ch_dir.exists():
                continue
            for f in sorted(ch_dir.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                if data["meta"]["confidence"] < args.threshold:
                    low_conf.append({
                        "ref": data["ref"],
                        "confidence": data["meta"]["confidence"],
                        "path": str(f.relative_to(Path("."))),
                    })
        quarantined = []
        q_dir = out_root / "_quarantine"
        if q_dir.exists():
            for f in sorted(q_dir.glob("*.json")):
                quarantined.append(str(f.relative_to(Path("."))))
        report = {
            "threshold": args.threshold,
            "low_confidence_count": len(low_conf),
            "quarantined_count": len(quarantined),
            "low_confidence": low_conf,
            "quarantined": quarantined,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        ap.error("specify --pilot, --full, --verse, or --report")


if __name__ == "__main__":
    main()
