from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTRACTS = ROOT / "contracts"
PROMPTS = ROOT / "prompts"

REQUIRED_OUTPUTS = {
    "answer_status",
    "suggested_questions",
    "action_suggestions",
    "related_contact_keys",
}
ANSWER_STATUSES = {"reliable", "limited", "not_found", "blocked"}
ACTION_TYPES = {"read", "ask", "prepare", "practice", "review", "other"}
DUE_HINTS = {"today", "within_3_days", "this_week", "no_date"}
TOPIC_KEYS = {
    "today_start",
    "company_business",
    "my_role",
    "current_project",
    "team_collaboration",
    "common_processes",
}
REQUIRED_PROMPTS = {
    "security-gate.md",
    "question-route.md",
    "evidence-judge.md",
    "answer-system.md",
    "follow-up-generator.md",
    "action-candidate-generator.md",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    schema = read_json(CONTRACTS / "workflow-outputs.schema.json")
    example = read_json(CONTRACTS / "workflow-output.example.json")
    contacts = read_json(CONTRACTS / "contact-keys.json")["contacts"]

    assert set(schema["required"]) == REQUIRED_OUTPUTS
    assert set(example) == REQUIRED_OUTPUTS
    assert example["answer_status"] in ANSWER_STATUSES
    assert len(example["suggested_questions"]) <= 3
    assert len(example["action_suggestions"]) <= 3
    assert len(example["related_contact_keys"]) <= 5

    contact_keys = [contact["key"] for contact in contacts]
    assert len(contact_keys) == len(set(contact_keys)), "contact keys must be unique"
    known_contact_keys = set(contact_keys)

    for action in example["action_suggestions"]:
        assert action["action_type"] in ACTION_TYPES
        assert action["due_hint"] in DUE_HINTS
        assert action["topic_key"] is None or action["topic_key"] in TOPIC_KEYS
        assert action["source"] == "agent_candidate"
        related_key = action["related_contact_key"]
        assert related_key is None or related_key in known_contact_keys

    assert set(example["related_contact_keys"]) <= known_contact_keys

    prompt_names = {path.name for path in PROMPTS.glob("*.md")}
    assert REQUIRED_PROMPTS <= prompt_names, (
        f"missing prompts: {sorted(REQUIRED_PROMPTS - prompt_names)}"
    )
    for prompt_name in REQUIRED_PROMPTS:
        assert (PROMPTS / prompt_name).read_text(encoding="utf-8").strip()

    print("Chatflow asset validation passed")
    print(f"prompts={len(REQUIRED_PROMPTS)}")
    print(f"contact_keys={len(contact_keys)}")
    print(f"example_actions={len(example['action_suggestions'])}")


if __name__ == "__main__":
    main()
