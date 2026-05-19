"""Unit tests for app/sources/psn.py — psnawp is mocked at the module boundary."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.sources.psn import check_npsso, fetch_library


def _make_trophy_title(
    np_communication_id: str = "NPWR12345_00",
    title_name: str = "God of War",
    title_icon_url: str = "https://example.com/gow.jpg",
    progress: int = 75,
):
    t = MagicMock()
    t.np_communication_id = np_communication_id
    t.title_name = title_name
    t.title_icon_url = title_icon_url
    t.progress = progress
    return t


def _make_title_stats(
    title_id: str = "PPSA01234_00",
    name: str = "God of War",
    image_url: str = "https://example.com/gow.jpg",
    play_duration: timedelta | None = timedelta(hours=12, minutes=30),
):
    s = MagicMock()
    s.title_id = title_id
    s.name = name
    s.image_url = image_url
    s.play_duration = play_duration
    return s


def _setup_client(mock_cls, trophy_titles=None, title_stats_list=None):
    client = MagicMock()
    user = MagicMock()
    user.trophy_titles.return_value = trophy_titles or []
    user.title_stats.return_value = title_stats_list or []
    client.user.return_value = user
    mock_cls.return_value = client
    return client, user


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_happy_path_with_playtime(mock_psnawp_cls):
    trophy = _make_trophy_title()
    stats = _make_title_stats(play_duration=timedelta(hours=12, minutes=30))
    _setup_client(mock_psnawp_cls, [trophy], [stats])

    result = fetch_library(npsso="valid_npsso", online_id="VaultTec_Trading")

    assert len(result) == 1
    item = result[0]
    assert item.psn_id == "NPWR12345_00"
    assert item.title == "God of War"
    assert item.trophy_progress_pct == 75
    assert item.hours_played == 12.5


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_platforms_mapped_to_igdb_names(mock_psnawp_cls):
    trophy = _make_trophy_title()
    ps4 = MagicMock()
    ps4.value = "PS4"
    ps5 = MagicMock()
    ps5.value = "PS5"
    trophy.title_platform = [ps4, ps5]
    _setup_client(mock_psnawp_cls, [trophy], [])

    result = fetch_library(npsso="valid_npsso", online_id="AnyUser")

    assert result[0].platforms == frozenset({"PlayStation 4", "PlayStation 5"})


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_unknown_platform_ignored(mock_psnawp_cls):
    trophy = _make_trophy_title()
    unknown = MagicMock()
    unknown.value = "UNKNOWN"
    trophy.title_platform = [unknown]
    _setup_client(mock_psnawp_cls, [trophy], [])

    result = fetch_library(npsso="valid_npsso", online_id="AnyUser")

    assert result[0].platforms == frozenset()


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_no_matching_stats_hours_is_none(mock_psnawp_cls):
    trophy = _make_trophy_title(title_name="Elden Ring")
    stats = _make_title_stats(name="God of War")  # different game
    _setup_client(mock_psnawp_cls, [trophy], [stats])

    result = fetch_library(npsso="valid_npsso", online_id="AnyUser")

    assert result[0].hours_played is None


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_private_profile(mock_psnawp_cls):
    from psnawp_api.core.psnawp_exceptions import PSNAWPForbiddenError

    client = MagicMock()
    user = MagicMock()
    user.trophy_titles.side_effect = PSNAWPForbiddenError("forbidden")
    client.user.return_value = user
    mock_psnawp_cls.return_value = client

    with pytest.raises(ValueError, match="psn_profile_private"):
        fetch_library(npsso="valid_npsso", online_id="PrivateUser")


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_invalid_online_id(mock_psnawp_cls):
    from psnawp_api.core.psnawp_exceptions import PSNAWPNotFoundError

    client = MagicMock()
    client.user.side_effect = PSNAWPNotFoundError("not found")
    mock_psnawp_cls.return_value = client

    with pytest.raises(ValueError, match="psn_invalid_online_id"):
        fetch_library(npsso="valid_npsso", online_id="NonExistent999")


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_npsso_invalid(mock_psnawp_cls):
    from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError

    mock_psnawp_cls.side_effect = PSNAWPAuthenticationError("bad npsso")

    with pytest.raises(ValueError, match="psn_npsso_invalid"):
        fetch_library(npsso="expired_npsso", online_id="AnyUser")


@patch("app.sources.psn.PSNAWP")
def test_check_npsso_valid_returns_none(mock_psnawp_cls):
    mock_psnawp_cls.return_value = MagicMock()

    result = check_npsso("valid_npsso")

    assert result is None


@patch("app.sources.psn.PSNAWP")
def test_check_npsso_auth_error_raises_npsso_invalid(mock_psnawp_cls):
    from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError

    mock_psnawp_cls.side_effect = PSNAWPAuthenticationError("bad npsso")

    with pytest.raises(ValueError, match="psn_npsso_invalid"):
        check_npsso("expired_npsso")


@patch("app.sources.psn.PSNAWP")
def test_check_npsso_server_error_raises_api_unavailable(mock_psnawp_cls):
    from psnawp_api.core.psnawp_exceptions import PSNAWPServerError

    mock_psnawp_cls.side_effect = PSNAWPServerError("server error")

    with pytest.raises(ValueError, match="psn_api_unavailable"):
        check_npsso("valid_npsso")


@patch("app.sources.psn.PSNAWP")
def test_fetch_library_network_timeout(mock_psnawp_cls):
    from requests.exceptions import Timeout

    client = MagicMock()
    user = MagicMock()
    user.trophy_titles.side_effect = Timeout("timeout")
    client.user.return_value = user
    mock_psnawp_cls.return_value = client

    with pytest.raises(ValueError, match="psn_api_unavailable"):
        fetch_library(npsso="valid_npsso", online_id="AnyUser")
