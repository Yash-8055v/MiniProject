"""
Phase 5: Ablation Study (60 claims × 6 configs)
================================================
Conducts an offline ablation study on the 5-layer credibility scoring logic.
It uses the raw search results fetched for each claim and recalculates the final
credibility score by selectively setting individual layer weights to 0 and
renormalizing the rest.
"""

import sys
import csv
import json
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"
ABLATION_CSV = RESULTS_DIR / "ablation_study.csv"

sys.path.insert(0, str(BASE_DIR.parent))
from tools.web_search import search_with_priority
from server.credibility_scorer import (
    layer1_source_tier,
    layer2_source_count,
    layer3_evidence_alignment,
    layer4_claim_verifiability,
    layer5_cross_agreement
)

# Standard weights
WEIGHTS = {
    "l1": 0.35,
    "l2": 0.20,
    "l3": 0.25,
    "l4": 0.10,
    "l5": 0.10
}

CONFIGS = {
    "Full_System": None,
    "No_L1": "l1",
    "No_L2": "l2",
    "No_L3": "l3",
    "No_L4": "l4",
    "No_L5": "l5",
}

COLUMNS = ["claim_id", "ground_truth", "config", "score_l1", "score_l2", "score_l3", "score_l4", "score_l5", "final_score"]

def run_ablation():
    claims = []
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)

    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 5: ABLATION STUDY ON CREDIBILITY SCORING")
    logger.info(f"{'='*60}\n")

    with open(ABLATION_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for i, claim in enumerate(claims):
            cid = claim["claim_id"]
            text = claim["claim_text"]
            gt = claim["ground_truth_verdict"]

            logger.info(f"[{i+1}/{len(claims)}] Fetching search for: {cid}")
            try:
                # We do this once per claim to save API limits/latency
                search_results = search_with_priority(text, num_results=8)
            except Exception as e:
                logger.error(f"Search failed for {cid}: {e}")
                continue

            # Calculate raw layers
            raw_l1 = layer1_source_tier(search_results)
            raw_l2 = layer2_source_count(search_results)
            raw_l3 = layer3_evidence_alignment(search_results)
            raw_l4 = layer4_claim_verifiability(text)
            raw_l5 = layer5_cross_agreement(search_results)

            for cfg_name, ablated_layer in CONFIGS.items():
                w = WEIGHTS.copy()
                if ablated_layer:
                    w[ablated_layer] = 0.0

                total_w = sum(w.values())
                # Normalize weights
                for k in w:
                    w[k] = w[k] / total_w

                final = (
                    raw_l1 * w["l1"] +
                    raw_l2 * w["l2"] +
                    raw_l3 * w["l3"] +
                    raw_l4 * w["l4"] +
                    raw_l5 * w["l5"]
                )

                writer.writerow({
                    "claim_id": cid,
                    "ground_truth": gt,
                    "config": cfg_name,
                    "score_l1": round(raw_l1, 2),
                    "score_l2": round(raw_l2, 2),
                    "score_l3": round(raw_l3, 2),
                    "score_l4": round(raw_l4, 2),
                    "score_l5": round(raw_l5, 2),
                    "final_score": round(final, 2)
                })
            
            # small delay to respect SERP API limits if necessary
            time.sleep(1)

    logger.info(f"\n  Ablation Study Completed! Saved to {ABLATION_CSV}")

if __name__ == "__main__":
    run_ablation()
