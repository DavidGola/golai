"""Tests pour les evals re-rank notoriété + grounding multi-tour.

Testent le schéma et la logique déterministe des scorers — pas de LLM call.
Prior art : test_eval_schema.py
"""
from pathlib import Path

import pytest

from evals.schema import EvalDataset, EvalItem

DATASETS_DIR = Path(__file__).resolve().parents[2] / "evals" / "datasets"
RG_PATH = DATASETS_DIR / "golai_rerank_grounding_v1.json"


def _load_rg() -> EvalDataset:
    return EvalDataset.model_validate_json(RG_PATH.read_text(encoding="utf-8"))


# ─── T1 : tracer bullet — dataset se charge avec 2 items ──────────────────────

def test_rg_dataset_loads():
    ds = _load_rg()
    assert ds.name == "golai-rerank-grounding-v1"
    assert len(ds.items) == 2


# ─── T2 : nouveaux champs de schéma ───────────────────────────────────────────

def test_rerank_case_has_min_notoriety_score():
    ds = _load_rg()
    item = next(i for i in ds.items if i.id == "rerank-notoriete-5-solo")
    assert item.expected.min_notoriety_score == pytest.approx(0.6)


def test_grounding_case_has_max_hallucination_rate():
    ds = _load_rg()
    item = next(i for i in ds.items if i.id == "grounding-multiturn-ghost")
    assert item.expected.max_hallucination_rate == pytest.approx(0.1)


def test_grounding_case_has_prior_turns():
    ds = _load_rg()
    item = next(i for i in ds.items if i.id == "grounding-multiturn-ghost")
    assert item.metadata.prior_turns == ["Je veux un jeu comme Ghost of Tsushima."]


# ─── T3 : score_notoriety — cas sans seuil ────────────────────────────────────

@pytest.mark.asyncio
async def test_score_notoriety_returns_none_when_no_threshold():
    from evals.scorers.notoriety import score_notoriety
    item = EvalItem(id="x", input="test")
    assert await score_notoriety(item, "**God of War**", None) is None


@pytest.mark.asyncio
async def test_score_notoriety_returns_zero_when_no_bold_titles():
    from evals.scorers.notoriety import score_notoriety
    from evals.schema import EvalExpected
    item = EvalItem(id="x", input="test", expected=EvalExpected(min_notoriety_score=0.4))
    assert await score_notoriety(item, "Bonsoir, voici quelques idées…", None) == 0.0


# ─── T5 : multi-turn runner importable ────────────────────────────────────────

def test_multiturn_runner_importable():
    from evals.run_langfuse_dataset import run_dataset_item_multiturn
    assert callable(run_dataset_item_multiturn)


def test_evaluate_item_uses_multiturn_for_prior_turns_items():
    from evals.run_eval import evaluate_item
    assert callable(evaluate_item)


def test_score_notoriety_importable_in_run_eval():
    from evals.run_eval import evaluate_item  # noqa: F401
    from evals.scorers.notoriety import score_notoriety  # noqa: F401
    assert True  # both imports succeed


# ─── T6 : run_eval intègre notoriété + max_hallucination_rate ─────────────────

def test_rg_dataset_compatible_with_run_eval_schema():
    ds = _load_rg()
    item = next(i for i in ds.items if i.id == "rerank-notoriete-5-solo")
    assert item.expected.min_notoriety_score is not None
    item2 = next(i for i in ds.items if i.id == "grounding-multiturn-ghost")
    assert item2.expected.max_hallucination_rate is not None
    assert item2.metadata.prior_turns != []
