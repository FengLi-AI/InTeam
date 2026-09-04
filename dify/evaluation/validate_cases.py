from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evaluation" / "rag-cases.json"
REGISTRY_PATH = ROOT / "knowledge-source" / "00-统一事实表.md"

EXPECTED_COUNTS = {
    "company_common": 20,
    "role_collaboration": 15,
    "project": 15,
    "unknown": 10,
}
REQUIRED_FIELDS = {
    "id",
    "category",
    "question",
    "expected_behavior",
    "expected_dataset",
    "expected_fact_ids",
    "required_terms",
}
FACT_ID_PATTERN = re.compile(r"\b(?:COM|POL|SEC|ROLE|COL|PROC|PROJ)-\d{3}\b")


def main() -> None:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    assert isinstance(cases, list), "cases must be a list"
    assert len(cases) == 60, f"expected 60 cases, got {len(cases)}"

    case_ids = [case.get("id") for case in cases]
    assert len(case_ids) == len(set(case_ids)), "case ids must be unique"

    counts = Counter(case.get("category") for case in cases)
    assert counts == Counter(EXPECTED_COUNTS), f"unexpected category counts: {counts}"

    registry_fact_ids = set(
        FACT_ID_PATTERN.findall(REGISTRY_PATH.read_text(encoding="utf-8"))
    )

    referenced_fact_ids: set[str] = set()
    for case in cases:
        missing_fields = REQUIRED_FIELDS - case.keys()
        assert not missing_fields, f"{case.get('id')} missing fields: {missing_fields}"
        assert isinstance(case["question"], str) and case["question"].strip()
        assert isinstance(case["required_terms"], list) and case["required_terms"]

        behavior = case["expected_behavior"]
        assert behavior in {"grounded", "not_found"}, (
            f"{case['id']} has invalid behavior: {behavior}"
        )

        fact_ids = set(case["expected_fact_ids"])
        if behavior == "grounded":
            assert fact_ids, f"{case['id']} must reference at least one fact"
            assert case["expected_dataset"] in {
                "company_common",
                "role_collaboration",
                "project",
            }
        else:
            assert not fact_ids, f"{case['id']} not_found case cannot reference facts"
            assert case["expected_dataset"] is None

        referenced_fact_ids.update(fact_ids)

    missing_fact_ids = referenced_fact_ids - registry_fact_ids
    assert not missing_fact_ids, f"fact ids missing from registry: {sorted(missing_fact_ids)}"

    print("RAG case validation passed")
    print(f"total={len(cases)}")
    for category, count in EXPECTED_COUNTS.items():
        print(f"{category}={count}")
    print(f"referenced_fact_ids={len(referenced_fact_ids)}")


if __name__ == "__main__":
    main()
