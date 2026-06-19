from __future__ import annotations

from pydantic import BaseModel, Field


class MustCiteProperty(BaseModel):
    hltb_main_lte: float | None = None
    hltb_main_gte: float | None = None
    status_in: list[str] | None = None
    developer_in: list[str] | None = None
    release_year: int | None = None
    mode_in: list[str] | None = None


class EvalDimensions(BaseModel):
    no_hallucination: bool | None = None
    library_anchored: bool | None = None
    solo_multi_diff: bool | None = None
    honest_no_invention: bool | None = None
    expert_tone: bool | None = None
    completeness: bool | None = None
    studio_reputation: bool | None = None


class EvalExpected(BaseModel):
    must_cite_one_of: list[str] = Field(default_factory=list)
    must_not_cite: list[str] = Field(default_factory=list)
    must_cite_property: MustCiteProperty | None = None
    min_word_count: int | None = None
    min_notoriety_score: float | None = None  # seuil calibré à 0.6 (60e percentile, run 2026-06-19)
    max_hallucination_rate: float | None = None  # seuil calibré à 0.1 (tolérance trigram, run 2026-06-19)
    dimensions: EvalDimensions = Field(default_factory=EvalDimensions)


class EvalProfile(BaseModel):
    preferred_playtime: str | None = None
    favorite_genres: list[str] = Field(default_factory=list)
    important_criteria: list[str] = Field(default_factory=list)


class EvalLibraryGame(BaseModel):
    title: str
    status: str | None = None
    hours_played: float | None = None
    user_rating: int | None = None
    genres: list[str] = Field(default_factory=list)
    hltb_main: float | None = None


class EvalMetadata(BaseModel):
    tags: list[str] = Field(default_factory=list)
    profile: EvalProfile = Field(default_factory=EvalProfile)
    library: list[EvalLibraryGame] = Field(default_factory=list)
    prior_turns: list[str] = Field(default_factory=list)


class EvalItem(BaseModel):
    id: str
    input: str
    metadata: EvalMetadata = Field(default_factory=EvalMetadata)
    expected: EvalExpected = Field(default_factory=EvalExpected)

    def to_runner_dict(self) -> dict:
        """Convert to the dict format expected by run_dataset_item."""
        return {
            "id": self.id,
            "input": self.input,
            "expected_output": {},
            "metadata": {
                "tags": self.metadata.tags,
                "profile": self.metadata.profile.model_dump(exclude_none=True),
                "library": [g.model_dump(exclude_none=True) for g in self.metadata.library],
            },
        }


class EvalDataset(BaseModel):
    name: str
    description: str = ""
    metadata: dict = Field(default_factory=dict)
    items: list[EvalItem]
