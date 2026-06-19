def rerank_by_notoriety(candidates: list[dict], alpha: float) -> list[dict]:
    """Re-classe les candidats en combinant similarité sémantique et notoriété.

    Formule : final = (1 - alpha) * sem_norm + alpha * notoriety
    - notoriety = max(p_steam, p_igdb), fallback 0.5 si les deux sont absents
    - sem_norm  = normalisation min-max de la similarité dans le set (0 si set uniforme)
    - alpha=0   → ordre sémantique pur ; alpha=1 → ordre notoriété pur
    """
    if not candidates:
        return []

    sims = [c.get("similarity", 0.0) for c in candidates]
    min_sim = min(sims)
    max_sim = max(sims)
    sim_range = max_sim - min_sim

    def _notoriety(c: dict) -> float:
        p_s = c.get("p_steam")
        p_i = c.get("p_igdb")
        if p_s is None and p_i is None:
            return 0.5
        return max(v for v in (p_s, p_i) if v is not None)

    def _score(c: dict) -> float:
        sem_norm = (c.get("similarity", 0.0) - min_sim) / sim_range if sim_range else 0.0
        return (1.0 - alpha) * sem_norm + alpha * _notoriety(c)

    return sorted(candidates, key=_score, reverse=True)
