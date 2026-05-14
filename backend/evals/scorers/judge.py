"""LLM-as-judge scorer using GPT-4o Mini (anti self-bias vs Haiku).

Returns a multi-dimensional score dict — only active dimensions are scored.
"""
from __future__ import annotations

import json
import os

import litellm

from evals.schema import EvalDimensions, EvalItem

_JUDGE_MODEL = "gpt-4o-mini"

_RUBRICS: dict[str, str] = {
    "pertinence": (
        "pertinence (1-5) : la réponse répond-elle à la question posée, "
        "avec une justification cohérente et ancrée dans le contexte ?\n"
        "  1 = hors sujet / inventions  2 = partiel  3 = correct mais superficiel  "
        "4 = bien justifié  5 = précis, adapté au profil, exemplaire"
    ),
    "expert_tone": (
        "expert_tone (1-5) : la réponse ressemble-t-elle à celle d'un vrai passionné "
        "de jeux vidéo — vocabulaire technique, opinions affirmées, références pointues, "
        "aucune platitude générique comme 'c'est un bon jeu' ?\n"
        "  1 = générique / sans avis  2 = superficiel  3 = correct mais plat  "
        "4 = ton de connaisseur  5 = voix d'expert passionné, références solides"
    ),
    "completeness": (
        "completeness (1-5) : la réponse couvre-t-elle les aspects importants de la question "
        "sans laisser de trous majeurs ? Pour une question complexe (saga, studio, comparaison), "
        "une réponse courte est insuffisante.\n"
        "  1 = réponse trop courte / incomplète  2 = effleure le sujet  3 = couvre l'essentiel  "
        "4 = développée et structurée  5 = exhaustive et bien organisée"
    ),
    "studio_reputation": (
        "studio_reputation (1-5) : quand la question porte sur un studio ou une licence, "
        "l'agent mentionne-t-il les forces ET les faiblesses récurrentes connues ? "
        "Ex: Ubisoft → open world fatigue + microtransactions / FromSoftware → difficulté signature + qualité constante.\n"
        "  1 = ignore les problèmes ou les qualités  2 = unidimensionnel  3 = mentionne les deux mais vaguement  "
        "4 = nuancé et informé  5 = analyse précise, exemples concrets, équilibre forces/faiblesses"
    ),
}


def _active_rubrics(dims: EvalDimensions) -> list[str]:
    keys = ["pertinence"]
    if dims.expert_tone:
        keys.append("expert_tone")
    if dims.completeness:
        keys.append("completeness")
    if dims.studio_reputation:
        keys.append("studio_reputation")
    return keys


def _build_system_prompt(dims: EvalDimensions) -> str:
    keys = _active_rubrics(dims)
    rubric_text = "\n\n".join(f"• {_RUBRICS[k]}" for k in keys)
    json_fields = ", ".join(f'"{k}": <int 1-5>' for k in keys)
    return (
        "Tu es un évaluateur expert en recommandation de jeux vidéo. "
        "Note la réponse de l'agent selon les critères suivants :\n\n"
        f"{rubric_text}\n\n"
        f'Réponds UNIQUEMENT en JSON : {{{json_fields}, "reason": "<1 phrase>"}}'
    )


def _build_user_prompt(item: EvalItem, output: str) -> str:
    profile = item.metadata.profile.model_dump(exclude_none=True)
    library = [g.model_dump(exclude_none=True) for g in item.metadata.library]
    return (
        f"Question : {item.input}\n\n"
        f"Profil : {json.dumps(profile, ensure_ascii=False)}\n"
        f"Bibliothèque : {json.dumps(library, ensure_ascii=False)}\n\n"
        f"Réponse de l'agent :\n{output}"
    )


async def judge_item(item: EvalItem, output: str) -> tuple[dict[str, int | None], str | None]:
    """Return (scores_dict, reason). Scores dict contains one key per active dimension."""
    dims = item.expected.dimensions
    active_keys = _active_rubrics(dims)

    if not os.environ.get("OPENAI_API_KEY"):
        return {k: None for k in active_keys}, "OPENAI_API_KEY not set — judge skipped"

    try:
        response = await litellm.acompletion(  # type: ignore[attr-defined]
            model=_JUDGE_MODEL,
            messages=[
                {"role": "system", "content": _build_system_prompt(dims)},
                {"role": "user", "content": _build_user_prompt(item, output)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
        )
        content: str = response.choices[0].message.content or ""  # type: ignore[union-attr]
        parsed = json.loads(content)

        scores: dict[str, int | None] = {}
        for k in active_keys:
            raw = parsed.get(k)
            if raw is not None:
                v = int(raw)
                if not 1 <= v <= 5:
                    raise ValueError(f"{k} score out of range: {v}")
                scores[k] = v
            else:
                scores[k] = None

        reason = str(parsed.get("reason", ""))
        return scores, reason

    except Exception as exc:
        return {k: None for k in active_keys}, f"judge error: {exc}"
