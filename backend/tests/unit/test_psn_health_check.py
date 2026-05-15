from unittest.mock import patch

from scripts.psn_health_check import run


@patch("scripts.psn_health_check.psn.check_npsso")
def test_run_valid_npsso_exits_zero(mock_check):
    mock_check.return_value = None

    code = run("valid_npsso")

    assert code == 0
    mock_check.assert_called_once_with("valid_npsso")


@patch("scripts.psn_health_check.psn.check_npsso")
def test_run_invalid_npsso_captures_sentry_and_exits_one(mock_check):
    mock_check.side_effect = ValueError("psn_npsso_invalid")

    with patch("scripts.psn_health_check.sentry_sdk") as mock_sentry:
        code = run("expired_npsso")

    assert code == 1
    mock_sentry.capture_message.assert_called_once_with(
        "PSN NPSSO expired or invalid", level="error"
    )


@patch("scripts.psn_health_check.psn.check_npsso")
def test_run_api_unavailable_exits_two_no_sentry(mock_check):
    mock_check.side_effect = ValueError("psn_api_unavailable")

    with patch("scripts.psn_health_check.sentry_sdk") as mock_sentry:
        code = run("valid_npsso")

    assert code == 2
    mock_sentry.capture_message.assert_not_called()
