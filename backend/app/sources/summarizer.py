import logging
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def summarize_reviews(
    reviews: list[str],
    title: str,
    genres: list[str] | None = None,
    steam_score: int | None = None,
    steam_total_reviews: int | None = None,
) -> str | None:
    if not reviews:
        return None

    genre_ctx = f" (genres : {', '.join(genres)})" if genres else ""
    score_ctx = ""
    if steam_score is not None:
        score_ctx = f"Contexte interne, ne le mentionne pas explicitement : {steam_score}% d'avis positifs"
        if steam_total_reviews:
            score_ctx += f" sur {steam_total_reviews} avis"
        score_ctx += ".\n"

    # Cap input: 30 reviews, 400 chars each.
    text = "\n".join(f"- {r.strip().replace('\n', ' ')[:400]}" for r in reviews[:30] if r.strip())
    prompt = (
        f"Tu écris pour une app française de recommandation de jeux vidéo.\n"
        f"Résume en français, en un paragraphe utile de 4 à 6 phrases, le sentiment des joueurs sur '{title}'{genre_ctx}.\n"
        f"{score_ctx}"
        f"Contraintes : synthétise uniquement le contenu qualitatif des avis, explique ce que les joueurs apprécient, "
        f"ce qui revient comme frustration ou limite, et le type de joueur à qui le jeu semble le mieux convenir. "
        f"N'amplifie pas une critique isolée, ne cite pas les avis, ne mentionne pas de score chiffré, ne fais pas de liste Markdown.\n\n"
        f"Avis Steam récents à synthétiser :\n{text}"
    )

    try:
        message = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        logger.warning("Summarizer failed for %r: %s", title, exc)
        return None
