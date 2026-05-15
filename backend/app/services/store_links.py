from app.models.game import Game
from app.schemas.store import StoreLink


def build_store_links(game: Game) -> list[StoreLink]:
    links: list[StoreLink] = []
    if game.steam_id is not None:
        links.append(StoreLink(
            platform="steam",
            url=f"https://store.steampowered.com/app/{game.steam_id}/",
        ))
    if game.psn_id is not None:
        links.append(StoreLink(
            platform="playstation",
            url=f"https://store.playstation.com/concept/{game.psn_id}",
        ))
    return links
