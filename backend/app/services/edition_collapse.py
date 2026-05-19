from collections import defaultdict
from datetime import datetime

_DATETIME_MIN = datetime.min


def collapse_editions(rows: list[dict]) -> list[dict]:
    """Filtre les éditions redondantes d'un résultat RAG.

    Règle : si un groupe (Original + descendants) contient un remaster ou expanded,
    seule la version la plus récente (non-remake) est conservée. Les remakes coexistent
    toujours avec leur Original. L'ordre RAG d'origine est préservé.
    """
    if not rows:
        return []

    def _id(row: dict) -> str:
        return str(row["id"])

    def _parent(row: dict) -> str | None:
        p = row.get("parent_game_id")
        return str(p) if p else None

    ids_in_results: set[str] = {_id(r) for r in rows}

    def root_id(row: dict) -> str:
        p = _parent(row)
        if p and p in ids_in_results:
            return p
        return _id(row)

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[root_id(row)].append(row)

    ids_to_keep: set[str] = set()
    for group in groups.values():
        has_remaster_or_expanded = any(
            r.get("edition_type") in ("remaster", "expanded") for r in group
        )
        if not has_remaster_or_expanded:
            ids_to_keep.update(_id(r) for r in group)
        else:
            for r in group:
                if r.get("edition_type") == "remake":
                    ids_to_keep.add(_id(r))
            non_remakes = [r for r in group if r.get("edition_type") != "remake"]
            newest = max(
                non_remakes,
                key=lambda r: r.get("release_date") or _DATETIME_MIN,
            )
            ids_to_keep.add(_id(newest))

    return [r for r in rows if _id(r) in ids_to_keep]
