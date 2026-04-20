# TruthCrew Evaluation Benchmark Report
**Date:** 2026-04-20 01:26:01

## 1. Dataset & Inter-Annotator Agreement
- **Total Claims Evaluated:** 60
- **Fleiss' Kappa:** 0.0371 (Slight agreement)
> *Note: Agreement measured across Llama-3.3-70B, Qwen3-32B, and Llama-3.1-8B acting as independent annotators.*

## 2. Comparative Performance (Baselines)
| System | Accuracy (4-class) | Accuracy (Binary) | Macro F1 | 95% Wilson CI |
|--------|--------------------|-------------------|----------|----------------|
| **TruthCrew** (n=25) | 32.0% | 64.0% | 0.240 | [0.172, 0.516] |
| **FakeBERT** (n=60) | 68.3% | 78.3% | 0.327 | [0.558, 0.787] |
| **Qwen3_ZS** (n=60) | 60.0% | 75.0% | 0.428 | [0.474, 0.714] |
| **LIAR_LogReg** (n=60) | 45.0% | 73.3% | 0.316 | [0.331, 0.575] |
| **Llama3.3_ZS** (n=60) | 61.7% | 73.3% | 0.499 | [0.490, 0.729] |

## 3. TruthCrew Analysis
### Execution Reliability
- **Successful Predictions:** 25
- **Failed/Empty Predictions:** 35
- **Accuracy on successfully processed claims (n=25):** 64.0% (binary) / 32.0% (4-class)
- **Overall accuracy strictly evaluating full dataset (n=60):** 26.7% (binary) / 13.3% (4-class)

**Failed Claim IDs (500 Server Error / Timeout / Unparsed):**
```text
boomlive_016, boomlive_017, boomlive_018, boomlive_019, boomlive_020, boomlive_021, boomlive_022, boomlive_023, manual_001, manual_002, manual_003, manual_004, manual_005, manual_006, manual_007, manual_008, manual_009, manual_010, manual_011, manual_012, manual_013, manual_014, manual_015, manual_016, manual_017, manual_018, manual_019, manual_020, manual_021, manual_022, manual_023, manual_024, manual_025, manual_026, manual_027
```

### Latency Statistics
- **Mean:** 8544 ms
- **Median:** 4430 ms
- **95th percentile:** 22012 ms
- *(Total LLM + Search overhead per claim)*

### Statistical Significance (McNemar's Test)
Comparing TruthCrew against baselines:
| Comparison | p-value | Significant (p < 0.05)? |
|------------|---------|-----------------------|
| TruthCrew vs LIAR_LogReg | 0.0 | Yes ✅ |
| TruthCrew vs FakeBERT | 0.0 | Yes ✅ |
| TruthCrew vs Llama3.3_ZS | 0.0001 | Yes ✅ |
| TruthCrew vs Qwen3_ZS | 0.0 | Yes ✅ |

## 4. Ablation Study: Credibility Scoring
This table shows the **average credibility score (0-100)** assigned to Real vs. Fake claims under different layer ablations (when a layer is removed and weights are renormalized).
A higher gap between Real and Fake scores indicates better discriminative power.

| Configuration | Avg Score (Real/True) | Avg Score (Fake) | Gap (Real - Fake) |
|---------------|------------------------|------------------|-------------------|
| Full_System | 85.5 | 68.3 | **17.1** |
| No_L1 | 89.5 | 73.6 | **15.9** |
| No_L2 | 81.8 | 60.8 | **21.0** |
| No_L3 | 84.2 | 70.0 | **14.2** |
| No_L4 | 87.7 | 70.6 | **17.1** |
| No_L5 | 84.6 | 67.6 | **17.1** |

---
*Report generated automatically by the TruthCrew Evaluation Framework.*