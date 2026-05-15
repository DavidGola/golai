from app.models.game import Game
from app.services.store_links import build_store_links


def test_game_with_psn_id_returns_playstation_store_link():
    game = Game(title="God of War", psn_id="NPWR12345_00")
    links = build_store_links(game)

    psn_link = next((l for l in links if l.platform == "playstation"), None)
    assert psn_link is not None
    assert psn_link.url == "https://store.playstation.com/concept/NPWR12345_00"


def test_game_without_psn_id_returns_no_playstation_link():
    game = Game(title="Some PC Game", steam_id=12345)
    links = build_store_links(game)

    assert not any(l.platform == "playstation" for l in links)
