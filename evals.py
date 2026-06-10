"""
Disagreement Engine Evaluation Suite

Runs the LLM system prompt against 5 golden retail scenarios and asserts:
1. The correct trap was detected (discount distortion, premium mirage, etc.)
2. Conflicts were identified (the engine doesn't just average)
3. The bet_lean is appropriate for the scenario (not Deeper Buy on traps, Deeper Buy on clean convergence)

Usage:
    python evals.py                    # Run all 5 cases
    python evals.py --verbose          # Show detailed per-case output
    python evals.py --case 1           # Run a specific case (1-5)

Requires DEEPSEEK_API_KEY in environment or .env file.
"""

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from synthesis.engine import synthesize, _clean_json
from synthesis.prompts import DISAGREEMENT_ENGINE_PROMPT

GOLDEN_FILE = Path(__file__).parent / "evals" / "golden_cases.json"
VERBOSE = "--verbose" in sys.argv
CASE_FILTER = None
for arg in sys.argv[1:]:
    if arg.startswith("--case="):
        CASE_FILTER = int(arg.split("=")[1]) - 1


def assert_condition(condition, message, case_name):
    if condition:
        return True, f"  ✅ {message}"
    else:
        return False, f"  ❌ FAIL: {message}"


def run_eval_case(case):
    results = []
    name = case["name"]
    expected = case.get("expected_trap", "unknown")

    synth = synthesize(case["trend"], case["nykaa"], case["myntra"], case["meesho"])
    conflicts = synth.get("conflicts", [])
    convergences = synth.get("convergences", [])
    bet = synth.get("bet_lean", "SKIP")

    # Run assertions
    for assertion in case.get("assertions", []):
        if assertion == "conflicts array must not be empty":
            ok, msg = assert_condition(len(conflicts) > 0, f"Conflicts detected: {len(conflicts)}", name)
            results.append((ok, msg))
        elif assertion == "at least one HIGH severity conflict":
            has_high = any(c.get("severity") == "HIGH" for c in conflicts)
            ok, msg = assert_condition(has_high, "HIGH severity conflict present", name)
            results.append((ok, msg))
        elif assertion.startswith("at least one conflict mentions"):
            terms = assertion.split("'")[1::2]
            found = any(any(t.lower() in json.dumps(c).lower() for t in terms) for c in conflicts)
            ok, msg = assert_condition(found, f"Conflict mentions: {terms}", name)
            results.append((ok, msg))
        elif assertion == "bet_lean should be Small Trial or Monitor Only":
            ok, msg = assert_condition(bet in ("Small Trial", "Monitor Only"), f"Bet lean '{bet}' is Small Trial or Monitor Only (correct for trap scenario)", name)
            results.append((ok, msg))
        elif assertion == "convergences array must not be empty":
            ok, msg = assert_condition(len(convergences) > 0, f"Convergences detected: {len(convergences)}", name)
            results.append((ok, msg))
        elif assertion == "bet_lean should be Deeper Buy":
            ok, msg = assert_condition(bet == "Deeper Buy", f"Bet lean '{bet}' is Deeper Buy (correct for clean convergence)", name)
            results.append((ok, msg))
        elif assertion == "conflicts should be minimal (0 or LOW only)":
            no_high = not any(c.get("severity") == "HIGH" for c in conflicts)
            no_med = not any(c.get("severity") == "MEDIUM" for c in conflicts)
            ok, msg = assert_condition(no_high and no_med, "No HIGH/MEDIUM conflicts (clean convergence)", name)
            results.append((ok, msg))

    passed = sum(1 for r in results if r[0])
    total = len(results)
    all_pass = passed == total

    if VERBOSE:
        print(f"\n{'='*60}")
        print(f"Case: {name}")
        print(f"Expected trap: {expected}")
        print(f"Bet lean: {bet}")
        print(f"Conflicts: {len(conflicts)}, Convergences: {len(convergences)}")
        for ok, msg in results:
            print(msg)
        if synth.get("headline"):
            print(f"\nHeadline: {synth['headline']}")
        if synth.get("_mode"):
            print(f"Mode: {synth['_mode']}")

    return {"name": name, "expected": expected, "passed": passed, "total": total,
            "all_pass": all_pass, "bet": bet, "conflict_count": len(conflicts),
            "convergence_count": len(convergences)}


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("⚠️  DEEPSEEK_API_KEY not set. Evals require the LLM to detect traps.")
        print("   Set it via: export DEEPSEEK_API_KEY=sk-...")
        print("   Or create a .env file in the project root.")
        return

    with open(GOLDEN_FILE) as f:
        data = json.load(f)

    cases = data["cases"]
    if CASE_FILTER is not None:
        cases = [cases[CASE_FILTER]]

    print(f"{'='*60}")
    print(f"Disagreement Engine — Evaluation Suite")
    print(f"Running {len(cases)} golden case(s)...")
    print(f"{'='*60}")

    results = []
    for case in cases:
        result = run_eval_case(case)
        results.append(result)

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    total_passed = sum(r["passed"] for r in results)
    total_assertions = sum(r["total"] for r in results)
    cases_passed = sum(1 for r in results if r["all_pass"])

    for r in results:
        status = "✅" if r["all_pass"] else "❌"
        print(f"  {status} {r['name']}: {r['passed']}/{r['total']} assertions  |  Bet: {r['bet']}  |  Conflicts: {r['conflict_count']}")

    print(f"\n  Overall: {total_passed}/{total_assertions} assertions passed ({cases_passed}/{len(results)} cases fully passed)")

    if total_passed == total_assertions:
        print("\n🎉 ALL GOLDEN CASES PASSED — The Disagreement Engine correctly detects all retail traps.")
    else:
        print(f"\n⚠️  {total_assertions - total_passed} assertion(s) failed. Review the verbose output for details.")

    return total_passed == total_assertions


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
