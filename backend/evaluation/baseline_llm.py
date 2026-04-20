"""
Phase 4c: Zero-Shot LLM Baselines (Llama 3.3 + Qwen 3)
========================================================
Direct zero-shot classification via Groq API.
No web search, no credibility scoring — pure LLM judgment.
Resumable: skips claim_ids already in prediction CSV.

Usage:
    python -m evaluation.baseline_llm
    python -m evaluation.baseline_llm --model llama    # only llama
    python -m evaluation.baseline_llm --model qwen     # only qwen
"""

import sys
import csv
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.key_manager import groq_manager

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"

MODELS = {
    "llama": {
        "model_id": "llama-3.3-70b-versatile",
        "output_csv": RESULTS_DIR / "llama_zeroshot_predictions.csv",
    },
    "qwen": {
        "model_id": "qwen/qwen3-32b",
        "output_csv": RESULTS_DIR / "qwen_zeroshot_predictions.csv",
    },
}

COLUMNS = ["claim_id", "claim_text", "ground_truth", "predicted_verdict", "confidence"]

ZS_PROMPT = """You are a fact-checking expert. Classify the following claim into EXACTLY ONE category:

- "True": The claim is factually correct.
- "False": The claim is factually incorrect or debunked.
- "Misleading": The claim has some truth but is framed deceptively or lacks context.
- "Unverifiable": There is insufficient evidence to determine truth or falsehood.

Claim: {claim_text}

Respond with ONLY a JSON object: {{"verdict": "...", "confidence": <0-100>}}
No other text."""


def normalize_verdict(raw: str) -> tuple:
    """Parse LLM response to extract verdict and confidence."""
    import re
    # Strip Qwen thinking blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Try JSON parse
    try:
        # Find JSON in response
        json_match = re.search(r'\{[^}]+\}', raw)
        if json_match:
            data = json.loads(json_match.group())
            verdict = data.get("verdict", "Unverifiable")
            confidence = data.get("confidence", 50)
            # Normalize verdict
            v = verdict.lower()
            if "false" in v:
                return "False", confidence
            if "misleading" in v:
                return "Misleading", confidence
            if "true" in v:
                return "True", confidence
            return "Unverifiable", confidence
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: keyword matching
    raw_lower = raw.lower()
    if "false" in raw_lower:
        return "False", 50
    if "misleading" in raw_lower:
        return "Misleading", 50
    if "true" in raw_lower:
        return "True", 50
    return "Unverifiable", 50


def load_claims() -> list:
    claims = []
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    return claims


def load_existing(csv_path: Path) -> set:
    existing = set()
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["claim_id"])
    return existing


def run_baseline(model_key: str):
    config = MODELS[model_key]
    model_id = config["model_id"]
    output_csv = config["output_csv"]

    claims = load_claims()
    existing = load_existing(output_csv)

    to_process = [c for c in claims if c["claim_id"] not in existing]

    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 4c: {model_key.upper()} ZERO-SHOT BASELINE")
    logger.info(f"  Model: {model_id}")
    logger.info(f"  Claims: {len(to_process)} remaining")
    logger.info(f"{'='*60}\n")

    write_header = not output_csv.exists() or len(existing) == 0

    correct = 0
    total = 0
    tok_limit = 300 if "qwen" in model_id.lower() else 80

    for i, claim in enumerate(to_process):
        cid = claim["claim_id"]
        text = claim["claim_text"]
        gt = claim["ground_truth_verdict"]

        logger.info(f"[{i+1}/{len(to_process)}] {cid}: {text[:50]}...")

        try:
            prompt = ZS_PROMPT.format(claim_text=text)
            raw = groq_manager.call(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=tok_limit,
            )
            pred, conf = normalize_verdict(raw)
        except Exception as e:
            logger.error(f"  ERROR: {e}")
            pred, conf = "Unverifiable", 0

        is_correct = (pred == gt) or (gt == "False" and pred == "Misleading")
        if is_correct:
            correct += 1
        total += 1

        logger.info(f"  Pred={pred} (conf={conf}%) GT={gt} | {'CORRECT' if is_correct else 'WRONG'}")

        mode = "w" if (write_header and i == 0) else "a"
        with open(output_csv, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            if write_header and i == 0:
                writer.writeheader()
            writer.writerow({
                "claim_id": cid,
                "claim_text": text[:200],
                "ground_truth": gt,
                "predicted_verdict": pred,
                "confidence": conf,
            })

        time.sleep(2)  # Rate limit

    logger.info(f"\n  {model_key.upper()} Results:")
    logger.info(f"  Accuracy: {correct}/{total} = {round(correct/total*100, 1)}%")
    logger.info(f"  Saved to: {output_csv}")


if __name__ == "__main__":
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        model = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "llama"
        run_baseline(model)
    else:
        # Run both
        run_baseline("llama")
        run_baseline("qwen")
