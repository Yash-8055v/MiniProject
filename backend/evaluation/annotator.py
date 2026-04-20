"""
Phase 2: Inter-Annotator Agreement via Three Groq Models
=========================================================
Uses 3 different model families on Groq as independent annotators.
Computes Fleiss' kappa for agreement measurement.
Resumable: skips claim_ids already in annotations.csv.

Usage:
    python -m evaluation.annotator              # full run
    python -m evaluation.annotator --test 5     # dry-run 5 claims
"""

import os
import sys
import csv
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add parent to path for key_manager
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.key_manager import groq_manager

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"
ANNOTATIONS_CSV = DATASET_DIR / "annotations.csv"

# Three annotator models (different families to reduce correlation)
ANNOTATORS = {
    "annotator_a": "llama-3.3-70b-versatile",     # Meta Llama 70B
    "annotator_b": "qwen/qwen3-32b",              # Alibaba Qwen 32B (different family)
    "annotator_c": "llama-3.1-8b-instant",         # Meta Llama 8B (smaller)
}

ANNOTATION_PROMPT = """You are labelling a claim for a misinformation benchmark. Classify the claim into EXACTLY ONE category:

- "True": Factually correct based on available evidence.
- "False": Factually incorrect or debunked.
- "Misleading": Contains some truth but lacks context or is framed deceptively.
- "Unverifiable": Insufficient evidence to determine.

Do NOT see any fact-checker verdict. Judge only from the claim text and your own knowledge.

Claim: {claim_text}
Language: {language}

Respond with ONLY the single-word label. No explanation."""

VALID_LABELS = {"True", "False", "Misleading", "Unverifiable"}
COLUMNS = ["claim_id", "annotator_a", "annotator_b", "annotator_c", "ground_truth_verdict"]


def load_claims() -> list:
    """Load claims from CSV."""
    claims = []
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    return claims


def load_existing_annotations() -> set:
    """Load already-annotated claim_ids."""
    existing = set()
    if ANNOTATIONS_CSV.exists():
        with open(ANNOTATIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["claim_id"])
    return existing


def normalize_label(raw: str) -> str:
    """Normalize LLM output to one of the 4 valid labels."""
    import re
    # Strip Qwen3 thinking blocks: <think>...</think>
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = raw.strip().strip('"').strip("'").strip(".")
    raw_lower = raw.lower()

    if "false" in raw_lower:
        return "False"
    if "misleading" in raw_lower:
        return "Misleading"
    if "true" in raw_lower:
        return "True"
    if "unverifiable" in raw_lower or "unverified" in raw_lower:
        return "Unverifiable"

    # Direct match
    for label in VALID_LABELS:
        if label.lower() == raw_lower:
            return label

    logger.warning(f"  Could not parse label: '{raw[:50]}', defaulting to 'Unverifiable'")
    return "Unverifiable"


def annotate_claim(claim_text: str, language: str, model: str) -> str:
    """Get annotation from a single Groq model."""
    prompt = ANNOTATION_PROMPT.format(claim_text=claim_text, language=language)
    messages = [{"role": "user", "content": prompt}]

    # Qwen3 needs more tokens for thinking mode output
    tok_limit = 200 if "qwen" in model.lower() else 10
    raw = groq_manager.call(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=tok_limit,
    )
    return normalize_label(raw)


def save_annotation(row: dict, write_header: bool = False):
    """Append one annotation row to CSV."""
    mode = "w" if write_header else "a"
    with open(ANNOTATIONS_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def compute_fleiss_kappa() -> float:
    """Compute Fleiss' kappa across the 3 annotators."""
    try:
        from statsmodels.stats.inter_rater import fleiss_kappa, aggregate_raters

        # Read annotations
        annotations = []
        with open(ANNOTATIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ratings = [row["annotator_a"], row["annotator_b"], row["annotator_c"]]
                annotations.append(ratings)

        if not annotations:
            return 0.0

        # Convert to numeric: True=0, False=1, Misleading=2, Unverifiable=3
        label_map = {"True": 0, "False": 1, "Misleading": 2, "Unverifiable": 3}
        numeric = []
        for ratings in annotations:
            numeric.append([label_map.get(r, 3) for r in ratings])

        # aggregate_raters expects (n_subjects, n_raters) array
        import numpy as np
        data = np.array(numeric)
        table, _ = aggregate_raters(data)
        kappa = fleiss_kappa(table, method="fleiss")
        return round(kappa, 4)

    except Exception as e:
        logger.error(f"Fleiss kappa computation failed: {e}")
        return 0.0


def interpret_kappa(kappa: float) -> str:
    """Interpret Fleiss' kappa value."""
    if kappa < 0:
        return "Poor (less than chance)"
    if kappa < 0.20:
        return "Slight agreement"
    if kappa < 0.40:
        return "Fair agreement"
    if kappa < 0.60:
        return "Moderate agreement"
    if kappa < 0.80:
        return "Substantial agreement"
    return "Near-perfect agreement"


def run_annotation(test_limit: int = None):
    """Main annotation pipeline."""
    claims = load_claims()
    existing = load_existing_annotations()

    if existing:
        logger.info(f"📋 Found {len(existing)} already-annotated claims, will skip")

    to_process = [c for c in claims if c["claim_id"] not in existing]
    if test_limit:
        to_process = to_process[:test_limit]

    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 2: ANNOTATING {len(to_process)} CLAIMS WITH 3 GROQ MODELS")
    logger.info(f"  Models: {list(ANNOTATORS.values())}")
    logger.info(f"{'='*60}\n")

    write_header = not ANNOTATIONS_CSV.exists() or len(existing) == 0

    for i, claim in enumerate(to_process):
        cid = claim["claim_id"]
        text = claim["claim_text"]
        lang = claim["language"]
        gt = claim["ground_truth_verdict"]

        logger.info(f"[{i+1}/{len(to_process)}] {cid}: {text[:60]}...")

        row = {"claim_id": cid, "ground_truth_verdict": gt}

        for ann_name, model in ANNOTATORS.items():
            try:
                label = annotate_claim(text, lang, model)
                row[ann_name] = label
                logger.info(f"  {ann_name} ({model}): {label}")
            except Exception as e:
                logger.error(f"  {ann_name} FAILED: {e}")
                row[ann_name] = "Unverifiable"

            # Rate limit: 2s between Groq calls
            time.sleep(2)

        # Save per-claim (resumable)
        save_annotation(row, write_header=(write_header and i == 0))
        logger.info(f"  GT={gt} | A={row['annotator_a']} B={row['annotator_b']} C={row['annotator_c']}")
        print()  # blank line for readability

    # Compute Fleiss' kappa
    logger.info(f"\n{'='*60}")
    logger.info(f"  COMPUTING FLEISS' KAPPA")
    logger.info(f"{'='*60}")

    kappa = compute_fleiss_kappa()
    interpretation = interpret_kappa(kappa)
    logger.info(f"  Fleiss' kappa = {kappa}")
    logger.info(f"  Interpretation: {interpretation}")

    # Save kappa result
    kappa_path = RESULTS_DIR / "fleiss_kappa.json"
    with open(kappa_path, "w") as f:
        json.dump({
            "fleiss_kappa": kappa,
            "interpretation": interpretation,
            "n_claims": len(claims),
            "n_annotators": 3,
            "models": list(ANNOTATORS.values()),
            "methodology": "Three LLM annotators on Groq (not humans). May have higher correlation than independent human raters.",
        }, f, indent=2)
    logger.info(f"  Saved to: {kappa_path}")

    # Print sample
    if test_limit:
        print(f"\n{'='*60}")
        print(f"  DRY-RUN SAMPLE ({test_limit} claims)")
        print(f"{'='*60}")
        with open(ANNOTATIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                print(f"  {row['claim_id']}: GT={row['ground_truth_verdict']} "
                      f"A={row['annotator_a']} B={row['annotator_b']} C={row['annotator_c']}")
        print(f"\n  Fleiss' kappa = {kappa} ({interpretation})")
        print(f"{'='*60}")


if __name__ == "__main__":
    test_limit = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        test_limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 5

    run_annotation(test_limit=test_limit)
