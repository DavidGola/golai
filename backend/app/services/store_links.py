from app.models.game import Game
from app.schemas.store import StoreLink


def build_store_links(game: Game) -> list[StoreLink]:
    links: list[StoreLink] = []
    if game.steam_id is not None:
        links.append(StoreLink(
            platform="steam",
            url=f"https://store.steampowered.com/app/{game.steam_id}/",
        ))
    # Futur : ajouter ici playstation_id, nintendo_eshop_id, xbox_id, etc.
    return links
