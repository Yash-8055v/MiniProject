"""
Phase 3: Run TruthCrew on all 60 claims
========================================
Calls the live TruthCrew backend API for each claim.
Resumable: skips claim_ids already in truthcrew_predictions.csv.

Usage:
    python -m evaluation.run_truthcrew
"""

import sys
import csv
import time
import json
import logging
import requests
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"
PREDICTIONS_CSV = RESULTS_DIR / "truthcrew_predictions.csv"

API_URL = "http://localhost:8000"
ENDPOINT = "/api/analyze-claim"

COLUMNS = [
    "claim_id", "claim_text", "ground_truth", "predicted_verdict",
    "confidence", "latency_ms", "credibility_score", "sources_count", "error",
]


def normalize_verdict(raw: str) -> str:
    """Map TruthCrew verdict to standard 4-class label."""
    v = raw.lower().strip()
    if "likely true" in v or v == "true":
        return "True"
    if "likely false" in v or v == "false":
        return "False"
    if "misleading" in v:
        return "Misleading"
    return "Unverifiable"


def load_claims() -> list:
    claims = []
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    return claims


def load_existing_predictions() -> set:
    existing = set()
    if PREDICTIONS_CSV.exists():
        with open(PREDICTIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["claim_id"])
    return existing


def save_prediction(row: dict, write_header: bool = False):
    mode = "w" if write_header else "a"
    with open(PREDICTIONS_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def run_truthcrew(test_limit: int = None):
    """Process all claims through TruthCrew API."""
    claims = load_claims()
    existing = load_existing_predictions()

    if existing:
        logger.info(f"Found {len(existing)} already-processed claims, will skip")

    to_process = [c for c in claims if c["claim_id"] not in existing]
    if test_limit:
        to_process = to_process[:test_limit]

    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 3: RUNNING TRUTHCREW ON {len(to_process)} CLAIMS")
    logger.info(f"  API: {API_URL}{ENDPOINT}")
    logger.info(f"{'='*60}\n")

    # Check server health first
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        resp.raise_for_status()
        logger.info(f"  Server health: OK")
    except Exception as e:
        logger.error(f"  Server not reachable: {e}")
        logger.error(f"  Please start the server: cd backend && python main.py")
        return

    write_header = not PREDICTIONS_CSV.exists() or len(existing) == 0
    correct = 0
    total = 0

    for i, claim in enumerate(to_process):
        cid = claim["claim_id"]
        text = claim["claim_text"]
        gt = claim["ground_truth_verdict"]

        logger.info(f"[{i+1}/{len(to_process)}] {cid}: {text[:60]}...")

        row = {
            "claim_id": cid,
            "claim_text": text[:200],
            "ground_truth": gt,
            "predicted_verdict": "",
            "confidence": 0,
            "latency_ms": 0,
            "credibility_score": 0,
            "sources_count": 0,
            "error": "",
        }

        start_time = time.time()
        try:
            resp = requests.post(
                f"{API_URL}{ENDPOINT}",
                json={"query": text},
                timeout=120,
            )
            latency = (time.time() - start_time) * 1000
            resp.raise_for_status()
            data = resp.json().get("data", {})

            raw_verdict = data.get("verdict", "Unknown")
            predicted = normalize_verdict(raw_verdict)
            confidence = data.get("confidence", 0)
            cred_score = data.get("credibility_score", 0)
            sources = len(data.get("sources", []))

            row["predicted_verdict"] = predicted
            row["confidence"] = confidence
            row["latency_ms"] = round(latency)
            row["credibility_score"] = cred_score
            row["sources_count"] = sources

            # Check correctness
            is_correct = (predicted == gt) or (gt == "False" and predicted == "Misleading")
            if is_correct:
                correct += 1
            total += 1

            status = "CORRECT" if is_correct else "WRONG"
            logger.info(f"  Pred={predicted} (conf={confidence}%) GT={gt} | {status} | {round(latency)}ms")

        except requests.Timeout:
            row["error"] = "TIMEOUT"
            row["latency_ms"] = round((time.time() - start_time) * 1000)
            logger.warning(f"  TIMEOUT (>120s)")
            total += 1
        except Exception as e:
            row["error"] = str(e)[:200]
            row["latency_ms"] = round((time.time() - start_time) * 1000)
            logger.error(f"  ERROR: {e}")
            total += 1

        save_prediction(row, write_header=(write_header and i == 0))

        # Delay between claims (TruthCrew does multiple Groq calls internally)
        if i < len(to_process) - 1:
            time.sleep(5)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"  TRUTHCREW RESULTS")
    logger.info(f"  Total: {total}, Correct: {correct}")
    if total > 0:
        logger.info(f"  Accuracy: {correct}/{total} = {round(correct/total*100, 1)}%")
    logger.info(f"  Saved to: {PREDICTIONS_CSV}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    test_limit = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        test_limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 5
    run_truthcrew(test_limit=test_limit)
