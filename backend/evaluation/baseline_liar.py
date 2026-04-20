"""
Phase 4a: LIAR Dataset Logistic Regression Baseline
=====================================================
Trains TF-IDF + LogReg on HuggingFace LIAR dataset.
Translates Hindi/Marathi claims to English before inference.

Usage:
    python -m evaluation.baseline_liar
"""

import csv
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"
PREDICTIONS_CSV = RESULTS_DIR / "liar_lr_predictions.csv"

COLUMNS = ["claim_id", "claim_text", "ground_truth", "predicted_verdict", "confidence"]


def translate_to_english(text: str) -> str:
    """Translate non-English text to English using deep-translator."""
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated if translated else text
    except Exception:
        return text


def load_claims() -> list:
    claims = []
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    return claims


def map_liar_to_binary(label: str) -> str:
    """Map LIAR 6-class labels to our 4-class system."""
    label = label.lower()
    if label in ("true", "mostly-true"):
        return "True"
    if label in ("false", "pants-fire"):
        return "False"
    if label in ("half-true", "barely-true"):
        return "Misleading"
    return "Unverifiable"


def run_baseline():
    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 4a: LIAR LOGISTIC REGRESSION BASELINE")
    logger.info(f"{'='*60}\n")

    # Step 1: Load LIAR dataset - try multiple approaches
    logger.info("  Loading LIAR dataset...")
    train_data = None
    try:
        from datasets import load_dataset
        dataset = load_dataset("liar")
        train_data = dataset
    except Exception as e1:
        logger.warning(f"  HuggingFace load failed: {e1}")
        # Try downloading TSV directly
        try:
            import io, requests
            logger.info("  Downloading LIAR TSV files directly...")
            base_url = "https://raw.githubusercontent.com/thiagorainmaker77/liar_dataset/master"
            
            def parse_liar_tsv(url):
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                items = []
                for line in resp.text.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        label = parts[1].strip()
                        statement = parts[2].strip()
                        if statement and label:
                            items.append({"statement": statement, "label": label})
                return items

            train_items = parse_liar_tsv(f"{base_url}/train.tsv")
            test_items = parse_liar_tsv(f"{base_url}/test.tsv")
            
            if train_items:
                train_data = {"train": train_items, "test": test_items}
                logger.info(f"  Loaded {len(train_items)} train, {len(test_items)} test from TSV")
            else:
                raise ValueError("No data parsed from TSV")
        except Exception as e2:
            logger.error(f"  TSV download also failed: {e2}")
            logger.info("  Falling back to simple keyword baseline...")
            _run_keyword_fallback()
            return

    if train_data is None:
        _run_keyword_fallback()
        return

    train = train_data["train"]
    test = train_data["test"]

    logger.info(f"  LIAR train: {len(train)} samples, test: {len(test)} samples")

    # Step 2: Train TF-IDF + LogReg
    logger.info("  Training TF-IDF + Logistic Regression...")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    # Map LIAR labels to binary
    train_texts = [item["statement"] for item in train]
    train_labels = [map_liar_to_binary(item["label"]) for item in train]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english")),
        ("lr", LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0)),
    ])

    pipeline.fit(train_texts, train_labels)

    # Evaluate on LIAR test set first
    test_texts = [item["statement"] for item in test]
    test_labels = [map_liar_to_binary(item["label"]) for item in test]
    liar_accuracy = pipeline.score(test_texts, test_labels)
    logger.info(f"  LIAR test accuracy: {liar_accuracy:.3f}")

    # Step 3: Predict on our 60 claims
    logger.info("  Running on our 60-claim benchmark...")
    claims = load_claims()

    write_header = True
    correct = 0
    total = 0

    with open(PREDICTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for claim in claims:
            text = claim["claim_text"]
            gt = claim["ground_truth_verdict"]
            lang = claim["language"]

            # Translate if not English
            if lang != "en":
                text = translate_to_english(text)

            pred = pipeline.predict([text])[0]
            proba = pipeline.predict_proba([text])[0]
            conf = round(max(proba) * 100)

            is_correct = (pred == gt) or (gt == "False" and pred == "Misleading")
            if is_correct:
                correct += 1
            total += 1

            writer.writerow({
                "claim_id": claim["claim_id"],
                "claim_text": text[:200],
                "ground_truth": gt,
                "predicted_verdict": pred,
                "confidence": conf,
            })

    logger.info(f"\n  LIAR LogReg Results:")
    logger.info(f"  Accuracy: {correct}/{total} = {round(correct/total*100, 1)}%")
    logger.info(f"  Saved to: {PREDICTIONS_CSV}")


def _run_keyword_fallback():
    """Simple keyword baseline if LIAR dataset fails to load."""
    claims = load_claims()

    false_keywords = ["fake", "false", "hoax", "debunk", "no evidence", "fabricated"]
    true_keywords = ["confirmed", "official", "launched", "declared", "passed"]

    with open(PREDICTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        correct = 0
        total = 0
        for claim in claims:
            text = claim["claim_text"].lower()
            gt = claim["ground_truth_verdict"]

            if any(kw in text for kw in false_keywords):
                pred = "False"
            elif any(kw in text for kw in true_keywords):
                pred = "True"
            else:
                pred = "Unverifiable"

            is_correct = (pred == gt) or (gt == "False" and pred == "Misleading")
            if is_correct:
                correct += 1
            total += 1

            writer.writerow({
                "claim_id": claim["claim_id"],
                "claim_text": text[:200],
                "ground_truth": gt,
                "predicted_verdict": pred,
                "confidence": 50,
            })

    logger.info(f"\n  Keyword Fallback Results:")
    logger.info(f"  Accuracy: {correct}/{total} = {round(correct/total*100, 1)}%")
    logger.info(f"  Saved to: {PREDICTIONS_CSV}")


if __name__ == "__main__":
    run_baseline()
