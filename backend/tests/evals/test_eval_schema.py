"""Fast schema validation tests for the v2 eval dataset — no LLM calls."""
from pathlib import Path

import pytest

from evals.schema import EvalDataset, EvalItem

DATASETS_DIR = Path(__file__).resolve().parents[2] / "evals" / "datasets"
V2_PATH = DATASETS_DIR / "golai_library_v2.json"


def _load_v2() -> EvalDataset:
    return EvalDataset.model_validate_json(V2_PATH.read_text(encoding="utf-8"))


def test_v2_dataset_loads():
    ds = _load_v2()
    assert ds.name == "golai-library-v2"
    assert len(ds.items) >= 20


def test_v2_all_items_have_unique_ids():
    ds = _load_v2()
    ids = [item.id for item in ds.items]
    assert len(ids) == len(set(ids)), "Duplicate item IDs detected"


def test_v2_all_items_have_input():
    ds = _load_v2()
    for item in ds.items:
        assert item.input.strip(), f"Empty input for item {item.id!r}"


@pytest.mark.parametrize(
    "case_id, expected_must_cite",
    [
        ("weekend-short-owned", ["A Short Hike"]),
        ("coop-not-started", ["It Takes Two", "Cuphead"]),
        ("completed-summary", ["Disco Elysium", "Elden Ring"]),
        ("avoid-long-game-short-constraint", ["What Remains of Edith Finch"]),
        ("status-aware-next-game", ["Into the Breach", "Firewatch"]),
    ],
)
def test_v2_must_cite_one_of(case_id: str, expected_must_cite: list[str]):
    ds = _load_v2()
    item = next(i for i in ds.items if i.id == case_id)
    for title in expected_must_cite:
        assert title in item.expected.must_cite_one_of, (
            f"Expected {title!r} in must_cite_one_of for {case_id!r}, "
            f"got {item.expected.must_cite_one_of}"
        )


def test_v2_to_runner_dict_compat():
    ds = _load_v2()
    for item in ds.items:
        d = item.to_runner_dict()
        assert "id" in d
        assert "input" in d
        assert "expected_output" in d
        assert "metadata" in d
        assert "library" in d["metadata"]
        assert "profile" in d["metadata"]


def test_v2_catalog_cases_have_empty_library():
    catalog_ids = {"studio-naughty-dog", "release-year-2024", "solo-mythologie-grecque", "multi-guerre"}
    ds = _load_v2()
    for item in ds.items:
        if item.id in catalog_ids:
            assert item.metadata.library == [], f"Catalog case {item.id!r} should have empty library"


def test_v2_must_cite_property_structure():
    ds = _load_v2()
    item_map: dict[str, EvalItem] = {i.id: i for i in ds.items}

    weekend = item_map["weekend-short-owned"]
    assert weekend.expected.must_cite_property is not None
    assert weekend.expected.must_cite_property.hltb_main_lte == 20

    studio = item_map["studio-naughty-dog"]
    assert studio.expected.must_cite_property is not None
    assert studio.expected.must_cite_property.developer_in == ["Naughty Dog"]

    solo = item_map["solo-mythologie-grecque"]
    assert solo.expected.must_cite_property is not None
    assert "Single player" in (solo.expected.must_cite_property.mode_in or [])


def test_v2_deterministic_scorers_import():
    from evals.scorers.deterministic import score_must_cite_one_of, score_must_not_cite, score_library_anchored
    from evals.scorers.hallucination import score_hallucination
    from evals.scorers.judge import judge_item
    assert callable(score_must_cite_one_of)
    assert callable(score_must_not_cite)
    assert callable(score_library_anchored)
    assert callable(score_hallucination)
    assert callable(judge_item)


def test_v2_score_must_cite_one_of_logic():
    from evals.scorers.deterministic import score_must_cite_one_of
    ds = _load_v2()
    item = next(i for i in ds.items if i.id == "weekend-short-owned")

    assert score_must_cite_one_of(item, "Je te recommande **A Short Hike**, c'est parfait !") is True
    assert score_must_cite_one_of(item, "Lance **Persona 5 Royal** ce week-end.") is False


def test_v2_score_must_not_cite_logic():
    from evals.scorers.deterministic import score_must_not_cite
    ds = _load_v2()
    item = next(i for i in ds.items if i.id == "already-owned-similar")

    assert score_must_not_cite(item, "Essaie **Ori and the Will of the Wisps** !") is True
    assert score_must_not_cite(item, "Rejoue **Hollow Knight**, c'est excellent.") is False


def test_v2_score_library_anchored_logic():
    from evals.scorers.deterministic import score_library_anchored
    ds = _load_v2()
    item = next(i for i in ds.items if i.id == "weekend-short-owned")

    rate = score_library_anchored(item, "Je te recommande **A Short Hike** et **Persona 5 Royal**.")
    assert rate == 1.0

    rate_half = score_library_anchored(item, "Je te recommande **A Short Hike** et **Celeste**.")
    assert rate_half == 0.5


def test_v2_new_dimensions_in_schema():
    ds = _load_v2()
    item_map = {i.id: i for i in ds.items}

    ubisoft = item_map["studio-ubisoft"]
    assert ubisoft.expected.dimensions.studio_reputation is True
    assert ubisoft.expected.dimensions.expert_tone is True
    assert ubisoft.expected.dimensions.completeness is True
    assert ubisoft.expected.min_word_count == 100

    fromsoftware = item_map["studio-fromsoftware"]
    assert fromsoftware.expected.dimensions.studio_reputation is True
    assert fromsoftware.expected.dimensions.expert_tone is True
    assert fromsoftware.expected.dimensions.completeness is None

    expert_soulslike = item_map["expert-tone-soulslike"]
    assert expert_soulslike.expected.dimensions.expert_tone is True
    assert expert_soulslike.expected.dimensions.studio_reputation is None

    mass_effect = item_map["completeness-mass-effect"]
    assert mass_effect.expected.min_word_count == 150
    assert mass_effect.expected.dimensions.completeness is True


def test_v2_score_min_word_count_logic():
    from evals.scorers.deterministic import score_min_word_count
    ds = _load_v2()
    item = next(i for i in ds.items if i.id == "studio-ubisoft")

    short_output = "Ubisoft fait des jeux ouverts."
    long_output = " ".join(["mot"] * 150)

    assert score_min_word_count(item, short_output) is False
    assert score_min_word_count(item, long_output) is True


def test_v2_judge_active_rubrics():
    from evals.scorers.judge import _active_rubrics
    from evals.schema import EvalDimensions

    dims_full = EvalDimensions(expert_tone=True, completeness=True, studio_reputation=True)
    assert set(_active_rubrics(dims_full)) == {"pertinence", "expert_tone", "completeness", "studio_reputation"}

    dims_minimal = EvalDimensions()
    assert _active_rubrics(dims_minimal) == ["pertinence"]

    dims_expert_only = EvalDimensions(expert_tone=True)
    assert set(_active_rubrics(dims_expert_only)) == {"pertinence", "expert_tone"}


def test_v2_new_cases_have_valid_must_cite():
    ds = _load_v2()
    item_map = {i.id: i for i in ds.items}

    fromsoftware = item_map["studio-fromsoftware"]
    assert any(t in fromsoftware.expected.must_cite_one_of for t in ["Dark Souls", "Elden Ring", "Miyazaki"])

    expert = item_map["expert-tone-soulslike"]
    assert "Dark Souls" in expert.expected.must_cite_one_of or "FromSoftware" in expert.expected.must_cite_one_of
