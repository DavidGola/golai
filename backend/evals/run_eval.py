"""CLI eval runner for GolAi — extends run_langfuse_dataset with scoring."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

try:
    import httpcore as _httpcore  # noqa: F401
    _HTTPCORE_ERRORS = (_httpcore.ReadError, _httpcore.ConnectError, _httpcore.RemoteProtocolError)
except ImportError:
    _HTTPCORE_ERRORS = (OSError,)

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Désactiver Langfuse avant l'import des modules app — les runs d'eval sont
# synthétiques et ne doivent pas polluer les traces de production.
# Passer LANGFUSE_ENABLED=true explicitement dans l'env pour outrepasser.
os.environ.setdefault("LANGFUSE_ENABLED", "false")

from app.database import AsyncSessionLocal
from evals.run_langfuse_dataset import run_dataset_item
from evals.schema import EvalDataset, EvalItem
from evals.scorers.deterministic import score_item
from evals.scorers.hallucination import score_hallucination
from evals.scorers.judge import judge_item

DATASET_V2_PATH = BACKEND_DIR / "evals" / "datasets" / "golai_library_v2.json"
BASELINE_PATH = BACKEND_DIR / "evals" / "baseline_v1.json"

# Prix en $ par million de tokens (input / output / cache_read / cache_write)
_PRICING: dict[str, tuple[float, float, float, float]] = {
    "anthropic/claude-haiku-4-5-20251001": (0.80, 4.00, 0.08, 0.80),
    "anthropic/claude-haiku-4-5":          (0.80, 4.00, 0.08, 0.80),
    "anthropic/claude-sonnet-4-5":         (3.00, 15.00, 0.30, 3.75),
    "anthropic/claude-sonnet-4-6":         (3.00, 15.00, 0.30, 3.75),
}


def _estimate_cost_usd(model: str | None, usage: dict) -> float | None:
    if not model:
        return None
    pricing = _PRICING.get(model)
    if not pricing:
        return None
    p_in, p_out, p_cr, p_cw = pricing
    total = (
        usage.get("input_tokens", 0) * p_in / 1_000_000
        + usage.get("output_tokens", 0) * p_out / 1_000_000
        + usage.get("cache_read_tokens", 0) * p_cr / 1_000_000
        + usage.get("cache_write_tokens", 0) * p_cw / 1_000_000
    )
    return round(total, 6)


def _is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, _HTTPCORE_ERRORS):
        return True
    # httpcore errors wrapped as RuntimeError by stream_agent → run_dataset_item
    msg = str(exc).lower()
    return isinstance(exc, RuntimeError) and any(
        kw in msg for kw in ("bad file descriptor", "read error", "connect error", "remote protocol")
    )


async def evaluate_item(item: EvalItem, no_judge: bool = False, verbose: bool = False) -> dict:
    agent_result: dict = {}
    # Retry once on transient HTTP connection errors (stale pool connection after idle timeout).
    for attempt in range(2):
        try:
            agent_result = await run_dataset_item(item.to_runner_dict())
            break
        except Exception as exc:
            if attempt == 1 or not _is_connection_error(exc):
                raise
            await asyncio.sleep(1)
            print("(connexion perdue, retry…)", end=" ", flush=True)
    output = agent_result["answer"]

    if verbose:
        print(f"\n=== {item.id} ===")
        print(f"Q: {item.input}")
        print(f"A: {output[:600]}")

    async with AsyncSessionLocal() as db:
        det_scores = await score_item(item, output, db)
        hall_rate = await score_hallucination(item, output, db)

    if no_judge:
        judge_scores: dict[str, int | None] = {}
        reason: str | None = "judge skipped (--no-judge)"
    else:
        judge_scores, reason = await judge_item(item, output)

    scores = {**det_scores, "hallucination_rate": hall_rate, **judge_scores}

    if verbose:
        print(f"Scores: {json.dumps(scores, indent=2, ensure_ascii=False)}")
        if reason:
            print(f"Judge: {reason}")

    usage = agent_result.get("usage", {})
    cost_usd = _estimate_cost_usd(agent_result.get("model"), usage)

    return {
        "id": item.id,
        "input": item.input,
        "scores": scores,
        "agent_output": output,
        "judge_reason": reason,
        "model": agent_result.get("model"),
        "usage": {**usage, "estimated_cost_usd": cost_usd},
    }


async def run_dataset(
    dataset: EvalDataset,
    case_id: str | None,
    no_judge: bool,
    verbose: bool,
) -> dict:
    items = dataset.items
    if case_id:
        items = [i for i in items if i.id == case_id]
        if not items:
            raise SystemExit(f"Case {case_id!r} not found in dataset")

    results = []
    for item in items:
        print(f"Evaluating {item.id}...", end=" ", flush=True)
        try:
            result = await evaluate_item(item, no_judge=no_judge, verbose=verbose)
            results.append(result)
            print("done")
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"id": item.id, "error": str(exc), "scores": {}})

    all_scores = [r["scores"] for r in results if "scores" in r]

    def avg(key: str) -> float | None:
        values = [s[key] for s in all_scores if s.get(key) is not None]
        return round(mean(values), 3) if values else None

    total_cost = sum(
        r.get("usage", {}).get("estimated_cost_usd") or 0
        for r in results
        if "usage" in r
    )

    metrics = {
        "hallucination_rate": avg("hallucination_rate"),
        "library_anchor_rate": avg("library_anchor_rate"),
        "must_cite_pass_rate": avg("must_cite_one_of"),
        "must_not_cite_pass_rate": avg("must_not_cite"),
        "must_cite_property_rate": avg("must_cite_property"),
        "min_word_count_pass_rate": avg("min_word_count_ok"),
        "pertinence_mean": avg("pertinence"),
        "expert_tone_mean": avg("expert_tone"),
        "completeness_mean": avg("completeness"),
        "studio_reputation_mean": avg("studio_reputation"),
        "total_cost_usd": round(total_cost, 6) if total_cost else None,
    }

    return {
        "dataset": dataset.name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(results),
        "metrics": metrics,
        "items": results,
    }


def compare_vs_baseline(report: dict, baseline: dict) -> bool:
    """Return True if no regression detected. Print details on failure."""
    regressions = []
    checks = [
        ("hallucination_rate", "<=", 0.05),
        ("library_anchor_rate", ">=", -0.05),
        ("must_cite_pass_rate", ">=", -0.1),
        ("pertinence_mean", ">=", -0.5),
        ("expert_tone_mean", ">=", -0.5),
        ("completeness_mean", ">=", -0.5),
        ("studio_reputation_mean", ">=", -0.5),
    ]
    for metric, op, delta in checks:
        current = report["metrics"].get(metric)
        base = baseline["metrics"].get(metric)
        if current is None or base is None:
            continue
        if op == "<=" and current > base + delta:
            regressions.append(f"  FAIL {metric}: {current:.3f} > baseline {base:.3f} (threshold +{delta})")
        elif op == ">=" and current < base + delta:
            regressions.append(f"  FAIL {metric}: {current:.3f} < baseline {base:.3f} (threshold {delta:+.1f})")

    if regressions:
        print("\n=== Regressions detected ===")
        for r in regressions:
            print(r)
        return False

    print("\n=== No regression vs baseline ===")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="GolAi eval runner")
    parser.add_argument("--dataset", type=Path, default=DATASET_V2_PATH, help="Path to v2 dataset JSON")
    parser.add_argument("--case", default=None, help="Run a single case by ID")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to file")
    parser.add_argument("--baseline", action="store_true", help="Compare report to baseline_v1.json and exit 1 on regression")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge (no OPENAI_API_KEY required)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    raw = json.loads(args.dataset.read_text(encoding="utf-8"))
    dataset = EvalDataset.model_validate(raw)

    report = asyncio.run(run_dataset(dataset, args.case, args.no_judge, args.verbose))

    print("\n=== Metrics ===")
    for k, v in report["metrics"].items():
        print(f"  {k}: {v}")

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport saved to {args.output}")

    if args.baseline:
        if not BASELINE_PATH.exists():
            raise SystemExit(f"Baseline not found at {BASELINE_PATH}. Run without --baseline first to generate it.")
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        ok = compare_vs_baseline(report, baseline)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
