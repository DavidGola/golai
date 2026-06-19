import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_query
from app.ai.rerank import rerank_by_notoriety
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
        g.igdb_rating_count,
        g.metacritic_score,
        (g.opencritic_signals->>'score')::int AS opencritic_score,
        g.steam_score,
        g.steam_total_reviews,
        g.steam_signals,
        g.steam_players_2weeks,
        g.steam_owners_min,
        g.steam_owners_max,
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
        ) AS platforms,
        COALESCE(
            (SELECT string_agg(st.name, ', ' ORDER BY gst.vote_count DESC NULLS LAST)
             FROM games_steam_tags gst JOIN steam_tags st ON st.id = gst.tag_id
             WHERE gst.game_id = g.id),
            ''
        ) AS steam_tags"""

# Requête sémantique avec CTE percentiles catalogue et score de similarité.
# Le CTE calcule les percentiles sur l'ensemble du catalogue (couverture 93 % pour igdb_rating_count).
# pool_k ≈ 40 candidats sont récupérés puis re-classés par rerank_by_notoriety avant slice top_k.
_SEMANTIC_QUERY = text(f"""
    WITH percentiles AS (
        SELECT
            id,
            cume_dist() OVER (ORDER BY COALESCE(steam_total_reviews, 0)) AS p_steam,
            cume_dist() OVER (ORDER BY COALESCE(igdb_rating_count, 0))   AS p_igdb
        FROM games
    )
    SELECT {_COLUMNS},
        (1 - (e.embedding <=> CAST(:vec AS vector))) AS similarity,
        pct.p_steam,
        pct.p_igdb
    FROM games g
    JOIN game_embeddings e ON e.game_id = g.id
    JOIN percentiles pct ON pct.id = g.id
    WHERE e.is_active = true AND e.model_version = :model_version
    ORDER BY e.embedding <=> CAST(:vec AS vector)
    LIMIT :pool_k
""")

_SEMANTIC_QUERY_EXCLUDE = text(f"""
    WITH percentiles AS (
        SELECT
            id,
            cume_dist() OVER (ORDER BY COALESCE(steam_total_reviews, 0)) AS p_steam,
            cume_dist() OVER (ORDER BY COALESCE(igdb_rating_count, 0))   AS p_igdb
        FROM games
    )
    SELECT {_COLUMNS},
        (1 - (e.embedding <=> CAST(:vec AS vector))) AS similarity,
        pct.p_steam,
        pct.p_igdb
    FROM games g
    JOIN game_embeddings e ON e.game_id = g.id
    JOIN percentiles pct ON pct.id = g.id
    WHERE e.is_active = true AND e.model_version = :model_version AND NOT (g.id = ANY(:exclude_ids))
    ORDER BY e.embedding <=> CAST(:vec AS vector)
    LIMIT :pool_k
""")

_LEXICAL_QUERY = text(f"""
    SELECT {_COLUMNS}
    FROM games g
    WHERE g.title % :query
    ORDER BY similarity(g.title, :query) DESC
    LIMIT :lex_k
""")

_LEXICAL_QUERY_EXCLUDE = text(f"""
    SELECT {_COLUMNS}
    FROM games g
    WHERE g.title % :query AND NOT (g.id = ANY(:exclude_ids))
    ORDER BY similarity(g.title, :query) DESC
    LIMIT :lex_k
""")


async def retrieve_games(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    *,
    exclude_ids: set[uuid.UUID] | None = None,
    alpha: float = 0.0,
) -> list[dict]:
    if not query.strip():
        return []

    k = top_k or settings.rag_top_k
    pool_k = settings.rag_candidate_pool
    lex_k = min(5, k)
    metadata = {"top_k": str(k), "embedding_model": settings.embedding_model}
    exclude_list = list(exclude_ids) if exclude_ids else None

    with observe("rag.retrieve_games", input=captured_input(query), metadata=metadata) as observation:
        # Lexical pass (trigram) — catches title variants like "Portal 1" → "Portal"
        if exclude_list:
            lex_rows = await db.execute(_LEXICAL_QUERY_EXCLUDE, {"query": query, "lex_k": lex_k, "exclude_ids": exclude_list})
        else:
            lex_rows = await db.execute(_LEXICAL_QUERY, {"query": query, "lex_k": lex_k})
        lexical = [dict(row._mapping) for row in lex_rows]

        # Semantic pass — kNN vector search with expanded pool (rag_candidate_pool ≈ 40)
        vector = await embed_query(query)
        vec_str = "[" + ",".join(str(x) for x in vector) + "]"
        if exclude_list:
            vec_rows = await db.execute(
                _SEMANTIC_QUERY_EXCLUDE,
                {"vec": vec_str, "pool_k": pool_k, "model_version": settings.embedding_model, "exclude_ids": exclude_list},
            )
        else:
            vec_rows = await db.execute(
                _SEMANTIC_QUERY,
                {"vec": vec_str, "pool_k": pool_k, "model_version": settings.embedding_model},
            )
        semantic = [dict(row._mapping) for row in vec_rows]

        # Re-rank semantic pool par notoriété (les hits lexicaux gardent leur priorité
        # en tant que correspondances exactes de titre).
        lexical_ids = {row["id"] for row in lexical}
        semantic_filtered = [row for row in semantic if row["id"] not in lexical_ids]
        reranked_semantic = rerank_by_notoriety(semantic_filtered, alpha)

        results = (lexical + reranked_semantic)[:k]

        merged_meta = {
            **metadata,
            "alpha": str(alpha),
            "lexical_count": str(len(lexical)),
            "vector_count": str(len(semantic)),
            "merged_count": str(len(results)),
        }
        output = [
            {"id": row.get("id"), "title": row.get("title")}
            for row in results
        ] if settings.langfuse_capture_content else {"result_count": len(results)}
        safe_update(observation, output=output, metadata=merged_meta)
        return results
