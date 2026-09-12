"""Run the fixed synthetic validator dataset: python -m evals.run."""

from datetime import datetime
import json
from pathlib import Path

from travel.domain import validate_plan


def main():
    dataset = json.loads((Path(__file__).parent / "datasets" / "validator.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(dataset["now"])
    results = []
    for case in dataset["cases"]:
        actual = sorted({issue["code"] for issue in validate_plan(case["plan"], now)})
        expected = sorted(case["expected_issue_codes"])
        results.append({"id": case["id"], "passed": actual == expected,
                        "expected_issue_codes": expected, "actual_issue_codes": actual})
    passed = sum(result["passed"] for result in results)
    print(json.dumps({"dataset": dataset["name"], "synthetic": True,
                      "frozen_now": dataset["now"], "cases": len(results), "passed": passed,
                      "constraint_case_accuracy": passed / len(results) if results else None,
                      "scope": "Exact issue-code agreement on synthetic constraints; does not measure actual route, price, or source accuracy.",
                      "results": results}, ensure_ascii=False, indent=2))
    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
