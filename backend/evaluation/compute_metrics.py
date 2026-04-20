"""
Phase 6: Compute All Metrics and Generate Report
==================================================
Reads predictions from all systems/baselines and computes:
- 4-class and binary accuracy
- Macro/weighted F1
- Per-class precision/recall/F1
- Confusion matrices (CSV + PNG)
- Per-language breakdown
- Latency stats (TruthCrew only)
- McNemar's test (TruthCrew vs each baseline)
- 95% Wilson CI

Usage:
    python -m evaluation.compute_metrics
"""

import csv
import json
import logging
import math
from pathlib import Path
from collections import Counter

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
CM_DIR = RESULTS_DIR / "confusion_matrices"
CM_DIR.mkdir(parents=True, exist_ok=True)

CLAIMS_CSV = DATASET_DIR / "claims_60.csv"

SYSTEMS = {
    "TruthCrew": RESULTS_DIR / "truthcrew_predictions.csv",
    "LIAR_LogReg": RESULTS_DIR / "liar_lr_predictions.csv",
    "FakeBERT": RESULTS_DIR / "fakebert_predictions.csv",
    "Llama3.3_ZS": RESULTS_DIR / "llama_zeroshot_predictions.csv",
    "Qwen3_ZS": RESULTS_DIR / "qwen_zeroshot_predictions.csv",
}

LABELS = ["True", "False", "Misleading", "Unverifiable"]
BINARY_MAP = {"True": "Real", "False": "Fake", "Misleading": "Fake", "Unverifiable": "Real"}

def normalize_verdict(verdict: str) -> str:
    """Normalize predicted verdict strings to standard 4-class labels."""
    if not verdict:
        return ""
    v = verdict.lower().strip()
    if v in ("likely_false", "false"):
        return "False"
    if v in ("likely_true", "true", "credible"):
        return "True"
    if v == "misleading":
        return "Misleading"
    if v == "unverifiable":
        return "Unverifiable"
    return verdict



def load_predictions(csv_path: Path) -> list:
    """Load predictions from a CSV file."""
    if not csv_path.exists():
        return []
    preds = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "predicted_verdict" in row:
                row["predicted_verdict"] = normalize_verdict(row["predicted_verdict"])
            preds.append(row)
    return preds


def load_claims() -> dict:
    """Load claims indexed by claim_id."""
    claims = {}
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims[row["claim_id"]] = row
    return claims


def compute_accuracy(preds: list) -> dict:
    """Compute 4-class and binary accuracy, tracking failures separately."""
    total_successful = 0
    correct_4class = 0
    correct_binary = 0
    failed_claims = []
    total_claims = len(preds)

    for p in preds:
        gt = p["ground_truth"]
        pred = p["predicted_verdict"]
        if not gt or not pred or pred in ("error", "timeout", "TIMEOUT"):
            failed_claims.append(p["claim_id"])
            continue

        total_successful += 1

        # 4-class accuracy
        if pred == gt:
            correct_4class += 1

        # Binary accuracy (False+Misleading = Fake, True+Unverifiable = Real)
        gt_bin = BINARY_MAP.get(gt, "Real")
        pred_bin = BINARY_MAP.get(pred, "Real")
        if gt_bin == pred_bin:
            correct_binary += 1

    if total_successful == 0:
        return {
            "accuracy_4class": 0, "accuracy_binary": 0, "total": 0, 
            "total_claims": total_claims, "failed_claims": failed_claims, 
            "accuracy_4class_full": 0, "accuracy_binary_full": 0
        }

    return {
        "accuracy_4class": round(correct_4class / total_successful, 4),
        "accuracy_binary": round(correct_binary / total_successful, 4),
        "accuracy_4class_full": round(correct_4class / total_claims, 4) if total_claims > 0 else 0,
        "accuracy_binary_full": round(correct_binary / total_claims, 4) if total_claims > 0 else 0,
        "correct_4class": correct_4class,
        "correct_binary": correct_binary,
        "total": total_successful,
        "total_claims": total_claims,
        "failed_claims": failed_claims,
    }


def compute_f1(preds: list) -> dict:
    """Compute macro and weighted F1."""
    from sklearn.metrics import f1_score, precision_recall_fscore_support

    gt_labels = []
    pred_labels = []
    for p in preds:
        gt = p["ground_truth"]
        pred = p["predicted_verdict"]
        if not gt or not pred or pred in ("error", "timeout", "TIMEOUT"):
            continue
        gt_labels.append(gt)
        pred_labels.append(pred)

    if not gt_labels:
        return {}

    all_labels = sorted(set(gt_labels + pred_labels))

    macro_f1 = f1_score(gt_labels, pred_labels, labels=all_labels, average="macro", zero_division=0)
    weighted_f1 = f1_score(gt_labels, pred_labels, labels=all_labels, average="weighted", zero_division=0)

    precision, recall, f1, support = precision_recall_fscore_support(
        gt_labels, pred_labels, labels=LABELS, zero_division=0
    )

    per_class = {}
    for i, label in enumerate(LABELS):
        per_class[label] = {
            "precision": round(precision[i], 4),
            "recall": round(recall[i], 4),
            "f1": round(f1[i], 4),
            "support": int(support[i]),
        }

    return {
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
    }


def compute_confusion_matrix(preds: list, system_name: str) -> list:
    """Compute and save confusion matrix."""
    from sklearn.metrics import confusion_matrix

    gt_labels = []
    pred_labels = []
    for p in preds:
        gt = p["ground_truth"]
        pred = p["predicted_verdict"]
        if not gt or not pred or pred in ("error", "timeout", "TIMEOUT"):
            continue
        gt_labels.append(gt)
        pred_labels.append(pred)

    if not gt_labels:
        return []

    cm = confusion_matrix(gt_labels, pred_labels, labels=LABELS)

    # Save as CSV
    cm_csv = CM_DIR / f"{system_name.lower()}_cm.csv"
    with open(cm_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([""] + LABELS)
        for i, label in enumerate(LABELS):
            writer.writerow([label] + list(cm[i]))

    # Save as PNG
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                    xticklabels=LABELS, yticklabels=LABELS, ax=ax)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Ground Truth")
        ax.set_title(f"Confusion Matrix: {system_name}")
        plt.tight_layout()
        plt.savefig(CM_DIR / f"{system_name.lower()}_cm.png", dpi=150)
        plt.close()
    except Exception as e:
        logger.warning(f"  Could not save PNG for {system_name}: {e}")

    return cm.tolist()


def compute_latency_stats(preds: list) -> dict:
    """Compute latency statistics from TruthCrew predictions."""
    latencies = []
    for p in preds:
        lat = p.get("latency_ms", "0")
        try:
            lat_ms = int(lat)
            if lat_ms > 0:
                latencies.append(lat_ms)
        except (ValueError, TypeError):
            continue

    if not latencies:
        return {}

    latencies.sort()
    return {
        "mean_ms": round(np.mean(latencies)),
        "median_ms": round(np.median(latencies)),
        "p95_ms": round(np.percentile(latencies, 95)),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "n_samples": len(latencies),
    }


def wilson_ci(correct: int, total: int, z: float = 1.96) -> tuple:
    """Compute 95% Wilson confidence interval."""
    if total == 0:
        return (0, 0)
    p = correct / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    return (round(max(0, center - margin), 4), round(min(1, center + margin), 4))


def mcnemar_test(preds_a: list, preds_b: list) -> dict:
    """McNemar's test comparing two systems."""
    from scipy.stats import chi2

    # Build claim_id -> correct map
    def correctness_map(preds):
        m = {}
        for p in preds:
            gt = p["ground_truth"]
            pred = p["predicted_verdict"]
            if pred in ("error", "timeout", "TIMEOUT"):
                m[p["claim_id"]] = False
            else:
                m[p["claim_id"]] = (pred == gt) or (gt == "False" and pred == "Misleading")
        return m

    map_a = correctness_map(preds_a)
    map_b = correctness_map(preds_b)

    common_ids = set(map_a.keys()) & set(map_b.keys())
    if len(common_ids) < 10:
        return {"error": "Too few common predictions"}

    # Contingency table
    b_wrong_a_right = 0  # b
    b_right_a_wrong = 0  # c

    for cid in common_ids:
        a_correct = map_a[cid]
        b_correct = map_b[cid]
        if a_correct and not b_correct:
            b_wrong_a_right += 1
        elif not a_correct and b_correct:
            b_right_a_wrong += 1

    b = b_wrong_a_right
    c = b_right_a_wrong

    if b + c == 0:
        return {"chi2": 0, "p_value": 1.0, "significant": False, "b": b, "c": c}

    chi2_stat = (abs(b - c) - 1) ** 2 / (b + c)
    p_value = 1 - chi2.cdf(chi2_stat, df=1)

    return {
        "chi2": round(chi2_stat, 4),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "b_wrong_a_right": b,
        "b_right_a_wrong": c,
    }


def per_language_breakdown(preds: list, claims: dict) -> dict:
    """Compute accuracy per language."""
    lang_stats = {}
    for p in preds:
        cid = p["claim_id"]
        gt = p["ground_truth"]
        pred = p["predicted_verdict"]
        if pred in ("error", "timeout", "TIMEOUT"):
            continue

        claim = claims.get(cid, {})
        lang = claim.get("language", "en")

        if lang not in lang_stats:
            lang_stats[lang] = {"correct": 0, "total": 0}

        lang_stats[lang]["total"] += 1
        if pred == gt or (gt == "False" and pred == "Misleading"):
            lang_stats[lang]["correct"] += 1

    result = {}
    for lang, stats in lang_stats.items():
        if stats["total"] > 0:
            result[lang] = {
                "accuracy": round(stats["correct"] / stats["total"], 4),
                "correct": stats["correct"],
                "total": stats["total"],
            }
    return result


def run_metrics():
    logger.info(f"\n{'='*60}")
    logger.info(f"  PHASE 6: COMPUTING ALL METRICS")
    logger.info(f"{'='*60}\n")

    claims = load_claims()
    all_metrics = {}
    all_preds = {}

    for system_name, csv_path in SYSTEMS.items():
        logger.info(f"\n--- {system_name} ---")
        preds = load_predictions(csv_path)

        if not preds:
            logger.warning(f"  No predictions found at {csv_path}")
            continue

        all_preds[system_name] = preds

        acc = compute_accuracy(preds)
        f1_metrics = compute_f1(preds)
        cm = compute_confusion_matrix(preds, system_name)
        lang_breakdown = per_language_breakdown(preds, claims)

        # Wilson CI
        ci = wilson_ci(acc.get("correct_4class", 0), acc.get("total", 0))

        metrics = {
            "system": system_name,
            **acc,
            **f1_metrics,
            "wilson_ci_95": ci,
            "per_language": lang_breakdown,
        }

        # Latency (TruthCrew only)
        if system_name == "TruthCrew":
            latency = compute_latency_stats(preds)
            metrics["latency"] = latency

        all_metrics[system_name] = metrics

        logger.info(f"  Accuracy (4-class): {acc.get('accuracy_4class', 0):.1%}")
        logger.info(f"  Accuracy (binary): {acc.get('accuracy_binary', 0):.1%}")
        logger.info(f"  Macro F1: {f1_metrics.get('macro_f1', 0):.4f}")
        logger.info(f"  Wilson CI: {ci}")

    # McNemar's tests (TruthCrew vs each baseline)
    if "TruthCrew" in all_preds:
        logger.info(f"\n--- McNemar's Tests ---")
        mcnemar_results = {}
        tc_preds = all_preds["TruthCrew"]

        for name, preds in all_preds.items():
            if name == "TruthCrew":
                continue
            result = mcnemar_test(tc_preds, preds)
            mcnemar_results[f"TruthCrew_vs_{name}"] = result
            sig = "SIGNIFICANT" if result.get("significant") else "not significant"
            logger.info(f"  TruthCrew vs {name}: chi2={result.get('chi2', 0)}, "
                       f"p={result.get('p_value', 1)}, {sig}")

        all_metrics["mcnemar_tests"] = mcnemar_results

    # Save summary CSV
    summary_csv = RESULTS_DIR / "metrics_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Accuracy_4class", "Accuracy_binary",
                         "Macro_F1", "Weighted_F1", "Wilson_CI_lower",
                         "Wilson_CI_upper", "N"])
        for name, m in all_metrics.items():
            if name == "mcnemar_tests":
                continue
            ci = m.get("wilson_ci_95", (0, 0))
            writer.writerow([
                name,
                m.get("accuracy_4class", 0),
                m.get("accuracy_binary", 0),
                m.get("macro_f1", 0),
                m.get("weighted_f1", 0),
                ci[0], ci[1],
                m.get("total", 0),
            ])

    # Save full JSON
    full_json = RESULTS_DIR / "metrics_full.json"
    with open(full_json, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"\n  Summary saved to: {summary_csv}")
    logger.info(f"  Full metrics saved to: {full_json}")
    logger.info(f"  Confusion matrices saved to: {CM_DIR}/")

    return all_metrics


if __name__ == "__main__":
    run_metrics()
