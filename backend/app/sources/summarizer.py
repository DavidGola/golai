import json
import logging
from litellm import acompletion

logger = logging.getLogger(__name__)

VIBES_VOCAB = {
    "atmospheric", "cozy", "dark", "brutal", "cinematic", "exploratory",
    "competitive", "relaxing", "chaotic", "methodical", "narrative-driven",
    "mechanical", "surreal", "nostalgic", "minimalist", "epic", "intimate",
    "comedic", "melancholic", "tense", "strategic", "creative", "social",
    "mysterious", "action-packed",
}

EMOTIONAL_TONE_VOCAB = {
    "joyful", "melancholic", "terrifying", "heartwarming", "anxious",
    "peaceful", "epic", "tense", "contemplative", "exciting", "somber",
    "lighthearted", "dark", "hopeful", "bittersweet",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "complaints": {"type": "array", "items": {"type": "string"}},
        "target_audience": {"type": "string"},
        "vibes": {"type": "array", "items": {"type": "string", "enum": sorted(VIBES_VOCAB)}},
        "emotional_tone": {"type": "array", "items": {"type": "string", "enum": sorted(EMOTIONAL_TONE_VOCAB)}},
        "session_shape": {"type": "string", "enum": ["short", "medium", "long", "flexible"]},
        "pacing": {"type": "string", "enum": ["fast", "moderate", "slow", "varied"]},
        "difficulty": {"type": "string", "enum": ["casual", "moderate", "hard", "brutal"]},
        "replay_value": {"type": "string", "enum": ["low", "medium", "high"]},
        "art_style": {
            "type": "string",
            "enum": [
                "pixel", "hand-drawn", "3d-realistic", "3d-stylized", "cel-shaded",
                "minimalist", "voxel", "photorealistic", "retro-3d", "mixed",
            ],
        },
    },
    "required": [
        "summary", "strengths", "complaints", "target_audience",
        "vibes", "emotional_tone", "session_shape", "pacing",
        "difficulty", "replay_value", "art_style",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "Tu produis un JSON structuré qui résume le sentiment des joueurs sur un jeu vidéo. "
    "Respecte strictement les vocabulaires fermés pour `vibes`, `emotional_tone`, et les enums. "
    f"Valeurs autorisées pour vibes : {sorted(VIBES_VOCAB)}. "
    f"Valeurs autorisées pour emotional_tone : {sorted(EMOTIONAL_TONE_VOCAB)}. "
    "session_shape : short | medium | long | flexible. "
    "pacing : fast | moderate | slow | varied. "
    "difficulty : casual | moderate | hard | brutal. "
    "replay_value : low | medium | high. "
    "art_style : pixel | hand-drawn | 3d-realistic | 3d-stylized | cel-shaded | minimalist | voxel | photorealistic | retro-3d | mixed."
)


async def generate_steam_signals(
    reviews: list[str],
    title: str,
    genres: list[str],
    steam_score: int | None,
    steam_total_reviews: int | None,
) -> dict | None:
    if not reviews:
        return None

    score_ctx = ""
    if steam_score is not None:
        score_ctx = f"Score Steam : {steam_score}% positifs"
        if steam_total_reviews:
            score_ctx += f" sur {steam_total_reviews} avis"
        score_ctx += ". "

    genre_ctx = f"Genres : {', '.join(genres)}. " if genres else ""
    text = "\n".join(f"- {r.strip().replace(chr(10), ' ')[:400]}" for r in reviews[:30] if r.strip())

    user_prompt = (
        f"Jeu : {title}. {genre_ctx}{score_ctx}\n\n"
        f"Avis Steam :\n{text}"
    )

    try:
        response = await acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "steam_signals", "schema": _SCHEMA, "strict": True},
            },
            max_tokens=800,
        )
        content: str | None = response.choices[0].message.content  # type: ignore[union-attr]
        if not content:
            return None
        return json.loads(content)
    except Exception as exc:
        logger.warning("generate_steam_signals failed for %r: %s", title, exc)
        return None
