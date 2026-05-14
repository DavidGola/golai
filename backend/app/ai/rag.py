from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_query
from app.config import settings
from app.observability import captured_input, observe, safe_update

_COLUMNS = """
        g.id::text,
        g.title,
        g.developer,
        g.release_date,
        g.summary,
        g.hltb_main,
        g.igdb_rating,
        g.metacritic_score,
        g.opencritic_score,
        g.steam_score,
        g.steam_total_reviews,
        g.steam_reviews_summary,
        g.cover_url,
        g.steam_id,
        COALESCE(
            (SELECT string_agg(gr.name, ', ')
             FROM games_genres gg JOIN genres gr ON gr.id = gg.genre_id
             WHERE gg.game_id = g.id),
            ''
        ) AS genres,
        COALESCE(
            (SELECT string_agg(DISTINCT pl.name, ', ')
             FROM games_platforms gp JOIN platforms pl ON pl.id = gp.platform_id
             WHERE gp.game_id = g.id),
            ''
        ) AS platforms"""

_RAG_QUERY = text(f"""
    SELECT {_COLUMNS}
    FROM games g
    JOIN game_embeddings e ON e.game_id = g.id
    WHERE e.is_active = true AND e.model_version = :model_version
    ORDER BY e.embedding <=> CAST(:vec AS vector)
    LIMIT :top_k
""")

_LEXICAL_QUERY = text(f"""
    SELECT {_COLUMNS}
    FROM games g
    WHERE g.title % :query
    ORDER BY similarity(g.title, :query) DESC
    LIMIT :lex_k
""")


async def retrieve_games(db: AsyncSession, query: str, top_k: int | None = None) -> list[dict]:
    if not query.strip():
        return []

    k = top_k or settings.rag_top_k
    lex_k = min(5, k)
    metadata = {"top_k": str(k), "embedding_model": settings.embedding_model}

    with observe("rag.retrieve_games", input=captured_input(query), metadata=metadata) as observation:
        # Lexical pass (trigram) — catches title variants like "Portal 1" → "Portal"
        lex_rows = await db.execute(_LEXICAL_QUERY, {"query": query, "lex_k": lex_k})
        lexical = [dict(row._mapping) for row in lex_rows]

        # Semantic pass — unchanged kNN vector search
        vector = await embed_query(query)
        vec_str = "[" + ",".join(str(x) for x in vector) + "]"
        vec_rows = await db.execute(
            _RAG_QUERY,
            {"vec": vec_str, "top_k": k, "model_version": settings.embedding_model},
        )
        semantic = [dict(row._mapping) for row in vec_rows]

        # Merge: lexical hits first (high-confidence title match), then semantic, dedupe by id
        seen: set[str] = set()
        results: list[dict] = []
        for row in lexical + semantic:
            rid = row["id"]
            if rid not in seen:
                seen.add(rid)
                results.append(row)
        results = results[:k]

        merged_meta = {**metadata, "lexical_count": str(len(lexical)), "vector_count": str(len(semantic)), "merged_count": str(len(results))}
        output = [
            {"id": row.get("id"), "title": row.get("title")}
            for row in results
        ] if settings.langfuse_capture_content else {"result_count": len(results)}
        safe_update(observation, output=output, metadata=merged_meta)
        return results
