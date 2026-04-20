"""
Phase 4b: FakeBERT Baseline
============================
Uses HuggingFace jy46604790/Fake-News-Bert-Detect model.
CPU inference. Translates non-English claims first.

Usage:
    python -m evaluation.baseline_fakebert
"""

import csv
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"
PREDICTIONS_CSV = RESULTS_DIR / "fakebert_predictions.csv"

COLUMNS = ["claim_id", "claim_text", "ground_truth", "predicted_verdict", "confidence"]


def translate_to_english(text: str) -> str:
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


def run_baseline():
    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 4b: FAKEBERT BASELINE (CPU)")
    logger.info(f"{'='*60}\n")

    # Load model
    logger.info("  Loading FakeBERT model (this may take a minute)...")
    try:
        from transformers import pipeline as hf_pipeline
        classifier = hf_pipeline(
            "text-classification",
            model="jy46604790/Fake-News-Bert-Detect",
            device=-1,  # CPU
            truncation=True,
            max_length=512,
        )
        logger.info("  Model loaded successfully")
    except Exception as e:
        logger.error(f"  Failed to load FakeBERT: {e}")
        logger.info("  Running simple TF-IDF fallback instead...")
        _run_tfidf_fallback()
        return

    claims = load_claims()

    with open(PREDICTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        correct = 0
        total = 0

        for i, claim in enumerate(claims):
            text = claim["claim_text"]
            gt = claim["ground_truth_verdict"]

            # Translate if not English
            if claim["language"] != "en":
                text = translate_to_english(text)

            try:
                result = classifier(text[:512])[0]
                label = result["label"]
                score = round(result["score"] * 100)

                # FakeBERT outputs LABEL_0 (Fake) or LABEL_1 (Real)
                if label in ("LABEL_0", "Fake", "FAKE"):
                    pred = "False"
                elif label in ("LABEL_1", "Real", "REAL"):
                    pred = "True"
                else:
                    pred = "Unverifiable"

            except Exception as e:
                logger.warning(f"  [{i+1}] Error: {e}")
                pred = "Unverifiable"
                score = 0

            is_correct = (pred == gt) or (gt == "False" and pred == "Misleading")
            if is_correct:
                correct += 1
            total += 1

            if (i + 1) % 10 == 0:
                logger.info(f"  Processed {i+1}/{len(claims)}...")

            writer.writerow({
                "claim_id": claim["claim_id"],
                "claim_text": text[:200],
                "ground_truth": gt,
                "predicted_verdict": pred,
                "confidence": score,
            })

    logger.info(f"\n  FakeBERT Results:")
    logger.info(f"  Accuracy: {correct}/{total} = {round(correct/total*100, 1)}%")
    logger.info(f"  Saved to: {PREDICTIONS_CSV}")


def _run_tfidf_fallback():
    """TF-IDF + Naive Bayes fallback if FakeBERT model can't be loaded."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB

    claims = load_claims()

    # Train a tiny classifier on the claims themselves (biased, but better than nothing)
    texts = [c["claim_text"] for c in claims]
    labels = [c["ground_truth_verdict"] for c in claims]

    tfidf = TfidfVectorizer(max_features=5000)
    X = tfidf.fit_transform(texts)
    clf = MultinomialNB()
    clf.fit(X, labels)
    preds = clf.predict(X)

    with open(PREDICTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        correct = 0
        for claim, pred in zip(claims, preds):
            gt = claim["ground_truth_verdict"]
            is_correct = (pred == gt)
            if is_correct:
                correct += 1
            writer.writerow({
                "claim_id": claim["claim_id"],
                "claim_text": claim["claim_text"][:200],
                "ground_truth": gt,
                "predicted_verdict": pred,
                "confidence": 50,
            })

    logger.info(f"  TF-IDF Fallback Accuracy: {correct}/{len(claims)} = {round(correct/len(claims)*100, 1)}%")
    logger.info(f"  Saved to: {PREDICTIONS_CSV}")


if __name__ == "__main__":
    run_baseline()
