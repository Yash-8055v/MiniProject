# TruthCrew 180-Claim Evaluation Benchmark — Implementation Plan

## Overview
Build a labelled dataset of 180 fact-checked claims, run TruthCrew + 4 baselines,
compute metrics, and produce a final evaluation report for Chapter 5.

## API Keys Available (rotate on rate limit)
### Groq Keys (30 req/min per key):
1. YOUR_GROQ_KEY_1 (primary, from .env)
2. YOUR_GROQ_KEY_2
3. YOUR_GROQ_KEY_3

### SerpAPI Keys (250 free/month, 50/hour per key):
1. YOUR_SERPAPI_KEY_1 (primary, from .env)
2. YOUR_SERPAPI_KEY_2

## Backend
- URL: http://localhost:8000
- Endpoint: POST /api/analyze-claim  body: {"query": "..."}
- LLM: groq/llama-3.3-70b-versatile
- Credibility Weights: L1=0.35, L2=0.20, L3=0.25, L4=0.10, L5=0.10

## Phases & Status (check CHECKPOINT.txt for live status)

| Phase | Description | Est. Duration |
|-------|-------------|---------------|
| 0 | Install dependencies | 5 min |
| 1 | Scrape 180 claims (checkpoint after 10) | 20-30 min |
| 2 | 3-model annotation + Fleiss kappa | 30-45 min |
| 3 | Run TruthCrew on 180 claims | 2-3 hours |
| 4 | Run 4 baselines | 1.5-2 hours |
| 5 | Ablation study (60 claims × 6 configs) | 3-4 hours |
| 6 | Compute all metrics | 10 min |
| 7 | Generate FINAL_EVALUATION_REPORT.md | 10 min |

## Key Decisions
- Ablation: 60 claims (not full 180)
- Backend: localhost:8000
- FakeBERT: CPU inference (acceptable)
- SerpAPI: rotate keys when limit hit
- Groq: rotate keys when rate limited

## File Structure
```
evaluation/
├── IMPLEMENTATION_PLAN.md     ← this file
├── CHECKPOINT.txt             ← live progress tracker
├── requirements_eval.txt
├── key_manager.py             ← API key rotation logic
├── scraper.py                 ← Phase 1
├── annotator.py               ← Phase 2
├── run_truthcrew.py           ← Phase 3
├── baseline_liar.py           ← Phase 4
├── baseline_fakebert.py       ← Phase 4
├── baseline_llama.py          ← Phase 4
├── baseline_gemma.py          ← Phase 4
├── ablation.py                ← Phase 5
├── compute_metrics.py         ← Phase 6
├── dataset/
│   ├── claims_180.csv
│   ├── claims_180.json
│   └── annotations.csv
└── results/
    ├── truthcrew_predictions.csv
    ├── liar_lr_predictions.csv
    ├── fakebert_predictions.csv
    ├── llama_zeroshot_predictions.csv
    ├── gemma_zeroshot_predictions.csv
    ├── ablation_study.csv
    ├── metrics_summary.csv
    ├── confusion_matrices/
    ├── run_log.txt
    └── FINAL_EVALUATION_REPORT.md
```
