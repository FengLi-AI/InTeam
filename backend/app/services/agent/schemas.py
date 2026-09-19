from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RunRequest(StrictModel):
    question: str = Field(min_length=1, max_length=3000)
    scenario: Literal["company", "exhibition"] = "exhibition"
    parent_run_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=300)


class ReadArgs(StrictModel):
    document_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_-]+$")


class SuggestedAction(StrictModel):
    title: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=240)


class InformationGap(StrictModel):
    kind: Literal["task_input", "source_gap", "live_check"]
    text: str = Field(min_length=1, max_length=400)


class Preparation(StrictModel):
    status: Literal["completed", "needs_input", "limited"]
    title: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=16000)
    source_ids: list[str] = Field(default_factory=list, max_length=12)
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    information_gaps: list[InformationGap] = Field(default_factory=list, max_length=8)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, max_length=3)
