"""
Phase 7: Generate Final Evaluation Report
==========================================
Reads the metrics JSON and ablation CSV to generate a comprehensive
markdown report of TruthCrew's performance against baselines and
ablation results.
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
REPORT_PATH = BASE_DIR / "FINAL_EVALUATION_REPORT.md"

METRICS_JSON = RESULTS_DIR / "metrics_full.json"
ABLATION_CSV = RESULTS_DIR / "ablation_study.csv"
KAPPA_JSON = RESULTS_DIR / "fleiss_kappa.json"

def generate_report():
    logger.info("Generating Final Report...")

    # Load metrics
    try:
        with open(METRICS_JSON, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load metrics: {e}")
        return

    # Load kappa
    kappa_data = {"fleiss_kappa": "N/A", "interpretation": "N/A"}
    try:
        with open(KAPPA_JSON, "r", encoding="utf-8") as f:
            kappa_data = json.load(f)
    except Exception:
        pass

    # Process ablation data to get Mean Final Score for True vs False claims
    ablation_stats = {}
    try:
        with open(ABLATION_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Groups: Config -> Ground Truth -> List of scores
            for row in reader:
                cfg = row["config"]
                gt = row["ground_truth"]
                score = float(row["final_score"])
                
                # Map everything to binary True vs Fake
                is_real = (gt == "True" or gt == "Unverifiable")
                group = "Real" if is_real else "Fake/Misleading"
                
                if cfg not in ablation_stats:
                    ablation_stats[cfg] = {"Real": [], "Fake/Misleading": []}
                
                ablation_stats[cfg][group].append(score)
                
    except Exception as e:
        logger.warning(f"Failed to load ablation data or incomplete: {e}")

    md = [
        "# TruthCrew Evaluation Benchmark Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 1. Dataset & Inter-Annotator Agreement",
        f"- **Total Claims Evaluated:** 60",
        f"- **Fleiss' Kappa:** {kappa_data.get('fleiss_kappa')} ({kappa_data.get('interpretation')})",
        "> *Note: Agreement measured across Llama-3.3-70B, Qwen3-32B, and Llama-3.1-8B acting as independent annotators.*",
        "",
        "## 2. Comparative Performance (Baselines)",
        "| System | Accuracy (4-class) | Accuracy (Binary) | Macro F1 | 95% Wilson CI |",
        "|--------|--------------------|-------------------|----------|----------------|"
    ]

    # Systems comparison table
    # Sort systems with TruthCrew first, then others sorted by binary accuracy
    systems = list(metrics.keys())
    if "TruthCrew" in systems:
        systems.remove("TruthCrew")
        systems = ["TruthCrew"] + sorted(systems, key=lambda x: metrics[x].get("accuracy_binary", 0) if x != "mcnemar_tests" else 0, reverse=True)
    
    for sys in systems:
        if sys == "mcnemar_tests" or sys == "latency": continue
        m = metrics.get(sys, {})
        ci = m.get('wilson_ci_95', [0, 0])
        total = m.get('total', 60)
        n_str = f"n={total}"
        md.append(f"| **{sys}** ({n_str}) | {m.get('accuracy_4class', 0):.1%} | {m.get('accuracy_binary', 0):.1%} | {m.get('macro_f1', 0):.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] |")

    md.extend([
        "",
        "## 3. TruthCrew Analysis",
    ])
    
    # Execution Stats
    if "TruthCrew" in metrics:
        tc = metrics["TruthCrew"]
        tc_full_binary = tc.get("accuracy_binary_full", 0)
        tc_full_4class = tc.get("accuracy_4class_full", 0)
        failed_list = tc.get("failed_claims", [])
        
        md.extend([
            "### Execution Reliability",
            f"- **Successful Predictions:** {tc.get('total', 0)}",
            f"- **Failed/Empty Predictions:** {len(failed_list)}",
            f"- **Accuracy on successfully processed claims (n={tc.get('total', 0)}):** {tc.get('accuracy_binary', 0):.1%} (binary) / {tc.get('accuracy_4class', 0):.1%} (4-class)",
            f"- **Overall accuracy strictly evaluating full dataset (n=60):** {tc_full_binary:.1%} (binary) / {tc_full_4class:.1%} (4-class)",
            ""
        ])
        
        if failed_list:
            md.extend([
                "**Failed Claim IDs (500 Server Error / Timeout / Unparsed):**",
                "```text",
                ", ".join(failed_list),
                "```",
                ""
            ])
    
    # Latency Stats
    if "TruthCrew" in metrics and "latency" in metrics["TruthCrew"]:
        lat = metrics["TruthCrew"]["latency"]
        md.extend([
            "### Latency Statistics",
            f"- **Mean:** {lat.get('mean_ms', 0)} ms",
            f"- **Median:** {lat.get('median_ms', 0)} ms",
            f"- **95th percentile:** {lat.get('p95_ms', 0)} ms",
            f"- *(Total LLM + Search overhead per claim)*",
            ""
        ])

    # McNemar's tests
    if "mcnemar_tests" in metrics and metrics["mcnemar_tests"]:
        md.extend([
            "### Statistical Significance (McNemar's Test)",
            "Comparing TruthCrew against baselines:",
            "| Comparison | p-value | Significant (p < 0.05)? |",
            "|------------|---------|-----------------------|"
        ])
        for comp, res in metrics["mcnemar_tests"].items():
            baseline_name = comp.replace("TruthCrew_vs_", "")
            sig = "Yes ✅" if res.get("significant") else "No ❌"
            p = res.get("p_value", "N/A")
            md.append(f"| TruthCrew vs {baseline_name} | {p} | {sig} |")
        md.append("")

    # Ablation Study
    if ablation_stats:
        md.extend([
            "## 4. Ablation Study: Credibility Scoring",
            "This table shows the **average credibility score (0-100)** assigned to Real vs. Fake claims under different layer ablations (when a layer is removed and weights are renormalized).",
            "A higher gap between Real and Fake scores indicates better discriminative power.",
            "",
            "| Configuration | Avg Score (Real/True) | Avg Score (Fake) | Gap (Real - Fake) |",
            "|---------------|------------------------|------------------|-------------------|"
        ])
        
        # Calculate averages
        for cfg, groups in ablation_stats.items():
            real_scores = groups.get("Real", [])
            fake_scores = groups.get("Fake/Misleading", [])
            
            avg_real = sum(real_scores) / len(real_scores) if real_scores else 0
            avg_fake = sum(fake_scores) / len(fake_scores) if fake_scores else 0
            gap = avg_real - avg_fake
            
            md.append(f"| {cfg} | {avg_real:.1f} | {avg_fake:.1f} | **{gap:.1f}** |")

    md.extend([
        "",
        "---",
        "*Report generated automatically by the TruthCrew Evaluation Framework.*"
    ])

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    logger.info(f"Report successfully generated at: {REPORT_PATH}")

if __name__ == "__main__":
    generate_report()
