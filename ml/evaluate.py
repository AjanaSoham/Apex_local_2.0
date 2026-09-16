"""Run the small, versioned evaluation dataset without external test tooling."""

import json
from pathlib import Path

from candidate_service import analyze_candidate


def main() -> None:
    cases = json.loads(Path(__file__).with_name("evaluation_dataset.json").read_text(encoding="utf-8"))
    failures = []
    for case in cases:
        score = analyze_candidate(case["resume_text"], case["job_description"])["scores"]["overall"]
        valid = score >= case.get("expected_min_score", 0) and score <= case.get("expected_max_score", 100)
        print(f"{case['id']}: {score}% {'PASS' if valid else 'FAIL'}")
        if not valid:
            failures.append(case["id"])
    if failures:
        raise SystemExit(f"Evaluation failures: {', '.join(failures)}")


if __name__ == "__main__":
    main()
