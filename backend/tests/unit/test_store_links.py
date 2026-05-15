from app.models.game import Game
from app.services.store_links import build_store_links


def test_xbox_link_from_xbox_id():
    game = Game(title="Halo", xbox_id="1095224633")
    links = build_store_links(game)
    xbox = next(l for l in links if l.platform == "xbox")
    assert xbox.url == "https://www.xbox.com/games/store/1095224633"


def test_xbox_link_prefers_store_urls_when_present():
    game = Game(title="Halo", xbox_id="1095224633", store_urls={"xbox": "https://www.xbox.com/en-US/games/store/halo/ABC"})
    links = build_store_links(game)
    xbox = next(l for l in links if l.platform == "xbox")
    assert xbox.url == "https://www.xbox.com/en-US/games/store/halo/ABC"


def test_no_xbox_link_when_xbox_id_none():
    game = Game(title="Some Game")
    links = build_store_links(game)
    assert all(l.platform != "xbox" for l in links)
