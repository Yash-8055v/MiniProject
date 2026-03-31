"""
TruthCrew Accuracy Test
=======================
20 test cases: 10 known FAKE + 10 known TRUE claims
sourced from AltNews, BoomLive, and verified public facts.

Calls /api/analyze-claim and checks if verdict matches expected.
"""

import requests
import json
import time

API = "http://localhost:8000"

# fmt: off
TEST_CASES = [
    # ── KNOWN FAKE CLAIMS (expected: likely_false or likely_misleading) ──────
    {
        "claim": "5G towers cause COVID-19 and spread the coronavirus through radiation",
        "expected": "false",
        "source": "AltNews / BoomLive",
        "category": "Health + Technology"
    },
    {
        "claim": "COVID-19 vaccine contains microchips installed by Bill Gates to track people",
        "expected": "false",
        "source": "AltNews",
        "category": "Health"
    },
    {
        "claim": "Drinking cow urine cures cancer and all terminal diseases",
        "expected": "false",
        "source": "BoomLive",
        "category": "Health"
    },
    {
        "claim": "NASA confirmed that India's Diwali lights were visible from space",
        "expected": "false",
        "source": "AltNews — viral recurring hoax",
        "category": "Science"
    },
    {
        "claim": "WhatsApp will start charging users a monthly fee from next month",
        "expected": "false",
        "source": "BoomLive — recurring hoax every year",
        "category": "Technology"
    },
    {
        "claim": "Eating raw garlic and onion juice completely prevents and cures dengue fever",
        "expected": "false",
        "source": "FactChecker.in",
        "category": "Health"
    },
    {
        "claim": "Indian government is distributing free laptops to all students across India",
        "expected": "false",
        "source": "Vishvas News — recurring fake scheme",
        "category": "Government"
    },
    {
        "claim": "Petrol prices will be reduced to Rs 40 per litre after new government order",
        "expected": "false",
        "source": "BoomLive",
        "category": "Finance"
    },
    {
        "claim": "Albert Einstein failed mathematics in school and was a poor student",
        "expected": "false",
        "source": "Snopes — viral myth",
        "category": "History"
    },
    {
        "claim": "India has been declared the world's number one most peaceful country by UN",
        "expected": "false",
        "source": "AltNews",
        "category": "Politics"
    },

    # ── KNOWN TRUE CLAIMS (expected: likely_true) ────────────────────────────
    {
        "claim": "India launched Chandrayaan-3 mission to the Moon in July 2023",
        "expected": "true",
        "source": "ISRO official",
        "category": "Science"
    },
    {
        "claim": "India became the world's most populous country surpassing China in 2023",
        "expected": "true",
        "source": "UN Population Report 2023",
        "category": "Demographics"
    },
    {
        "claim": "India hosted the G20 Summit in New Delhi in September 2023",
        "expected": "true",
        "source": "PIB / Official",
        "category": "Politics"
    },
    {
        "claim": "Sachin Tendulkar scored 100 international centuries in cricket",
        "expected": "true",
        "source": "ICC / BCCI records",
        "category": "Sports"
    },
    {
        "claim": "India's first female President was Pratibha Patil elected in 2007",
        "expected": "true",
        "source": "Government of India",
        "category": "History"
    },
    {
        "claim": "WHO declared COVID-19 a pandemic in March 2020",
        "expected": "true",
        "source": "WHO official announcement",
        "category": "Health"
    },
    {
        "claim": "India won the ICC Cricket World Cup in 1983 and 2011",
        "expected": "true",
        "source": "ICC records",
        "category": "Sports"
    },
    {
        "claim": "India's GDP growth rate was 8.2 percent in the financial year 2023-24",
        "expected": "true",
        "source": "Ministry of Statistics India",
        "category": "Economy"
    },
    {
        "claim": "UPI digital payments crossed 10 billion transactions in a single month in India in 2023",
        "expected": "true",
        "source": "NPCI official data",
        "category": "Technology"
    },
    {
        "claim": "The Right to Education Act making free education mandatory for children was passed in India in 2009",
        "expected": "true",
        "source": "Government of India",
        "category": "Education"
    },
]
# fmt: on


def normalize_verdict(raw: str) -> str:
    """Map backend verdict string to 'true', 'false', or 'misleading'."""
    v = raw.lower().strip()
    if "likely true" in v or "true" in v:
        return "true"
    if "likely false" in v or "false" in v:
        return "false"
    if "misleading" in v:
        return "misleading"
    return "unverified"


def is_correct(expected: str, actual: str) -> bool:
    """Verdict matches if:
    - expected 'false' and actual is 'false' or 'misleading'
    - expected 'true' and actual is 'true'
    """
    if expected == "false":
        return actual in ("false", "misleading")
    return actual == expected


def run_test(case: dict, idx: int) -> dict:
    claim = case["claim"]
    expected = case["expected"]

    print(f"\n[{idx:02d}/20] {claim[:70]}...")
    print(f"       Expected: {expected.upper()} | Source: {case['source']}")

    try:
        resp = requests.post(
            f"{API}/api/analyze-claim",
            json={"query": claim},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]

        raw_verdict = data.get("verdict", "Unknown")
        confidence = data.get("confidence", 0)
        actual = normalize_verdict(raw_verdict)
        correct = is_correct(expected, actual)

        status = "✅ CORRECT" if correct else "❌ WRONG"
        print(f"       Got:      {actual.upper()} (confidence: {confidence}%) {status}")

        return {
            "claim": claim,
            "category": case["category"],
            "expected": expected,
            "actual": actual,
            "raw_verdict": raw_verdict,
            "confidence": confidence,
            "correct": correct,
        }

    except requests.Timeout:
        print("       ⏱  TIMEOUT (>60s)")
        return {"claim": claim, "category": case["category"],
                "expected": expected, "actual": "timeout",
                "raw_verdict": "timeout", "confidence": 0, "correct": False}
    except Exception as e:
        print(f"       💥 ERROR: {e}")
        return {"claim": claim, "category": case["category"],
                "expected": expected, "actual": "error",
                "raw_verdict": str(e), "confidence": 0, "correct": False}


def main():
    print("=" * 70)
    print("  TruthCrew Accuracy Test — 20 Claims (10 Fake + 10 True)")
    print("=" * 70)

    results = []
    for i, case in enumerate(TEST_CASES, 1):
        result = run_test(case, i)
        results.append(result)
        # Small delay to avoid hitting Groq rate limits
        if i < len(TEST_CASES):
            time.sleep(3)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    errors = sum(1 for r in results if r["actual"] in ("error", "timeout"))

    fake_cases = [r for r in results if r["expected"] == "false"]
    true_cases = [r for r in results if r["expected"] == "true"]
    fake_correct = sum(1 for r in fake_cases if r["correct"])
    true_correct = sum(1 for r in true_cases if r["correct"])

    print(f"\n  Fake claims:  {fake_correct}/{len(fake_cases)} correct")
    print(f"  True claims:  {true_correct}/{len(true_cases)} correct")
    print(f"  Errors/timeouts: {errors}")
    print(f"\n  OVERALL ACCURACY: {correct}/{total - errors} = "
          f"{round(correct / max(total - errors, 1) * 100)}%")

    print("\n  Detailed results:")
    print(f"  {'#':<3} {'Expected':<10} {'Got':<12} {'Conf':<6} {'Cat':<15} {'OK'}")
    print("  " + "-" * 60)
    for i, r in enumerate(results, 1):
        ok = "✅" if r["correct"] else "❌"
        print(f"  {i:<3} {r['expected'].upper():<10} {r['actual'].upper():<12} "
              f"{r['confidence']:<6} {r['category'][:14]:<15} {ok}")

    # Save JSON report
    with open("test_results.json", "w") as f:
        json.dump({
            "total": total,
            "correct": correct,
            "accuracy_percent": round(correct / max(total - errors, 1) * 100),
            "fake_accuracy": f"{fake_correct}/{len(fake_cases)}",
            "true_accuracy": f"{true_correct}/{len(true_cases)}",
            "results": results,
        }, f, indent=2)

    print("\n  Full results saved to test_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
