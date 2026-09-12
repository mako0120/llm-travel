"""Run the fixed synthetic validator dataset: python -m evals.run."""

from datetime import datetime
import json
from pathlib import Path

from travel.domain import validate_plan
from travel.optimizer import optimize
from travel.providers import FixtureRouteProvider


def validator_results():
    dataset = json.loads((Path(__file__).parent / "datasets" / "validator.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(dataset["now"])
    results = []
    for case in dataset["cases"]:
        actual = sorted({issue["code"] for issue in validate_plan(case["plan"], now)})
        expected = sorted(case["expected_issue_codes"])
        results.append({"id": case["id"], "passed": actual == expected,
                        "expected_issue_codes": expected, "actual_issue_codes": actual})
    passed = sum(result["passed"] for result in results)
    return {"dataset": dataset["name"], "cases": len(results), "passed": passed,
            "scope": "Exact issue-code agreement on synthetic constraints; does not measure actual route, price, or source accuracy.",
            "results": results}


def optimizer_results():
    dataset = json.loads((Path(__file__).parent / "datasets" / "optimizer.json").read_text(encoding="utf-8"))
    results = []
    for case in dataset["cases"]:
        matrix = {(origin, destination): minutes for origin, destination, minutes in case["matrix"]}
        actual = optimize(case["candidates"], FixtureRouteProvider(matrix, case["configured"]), **case["input"])["state"]
        results.append({"id": case["id"], "passed": actual == case["expected_state"],
                        "expected_state": case["expected_state"], "actual_state": actual})
    passed = sum(result["passed"] for result in results)
    return {"dataset": dataset["name"], "cases": len(results), "passed": passed,
            "scope": "Fixture-only state agreement; does not measure real route availability, travel-time accuracy, or traveler satisfaction.",
            "results": results}


def main():
    validator = validator_results()
    optimizer = optimizer_results()
    cases, passed = validator["cases"] + optimizer["cases"], validator["passed"] + optimizer["passed"]
    print(json.dumps({"synthetic": True, "cases": cases, "passed": passed,
                      "constraint_case_accuracy": passed / cases if cases else None,
                      "suites": [validator, optimizer]}, ensure_ascii=False, indent=2))
    return 0 if cases and passed == cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
