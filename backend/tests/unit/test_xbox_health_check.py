from unittest.mock import patch

from scripts.xbox_health_check import run


@patch("scripts.xbox_health_check.xbox.check_api_key")
def test_run_valid_key_exits_zero(mock_check):
    mock_check.return_value = None
    assert run("valid-key") == 0


@patch("scripts.xbox_health_check.xbox.check_api_key")
def test_run_invalid_key_captures_sentry_error_and_exits_one(mock_check):
    mock_check.side_effect = ValueError("xbox_api_key_invalid")
    with patch("scripts.xbox_health_check.sentry_sdk") as mock_sentry:
        code = run("bad-key")
    assert code == 1
    mock_sentry.capture_message.assert_called_once_with(
        "OpenXBL API key invalid", level="error"
    )


@patch("scripts.xbox_health_check.xbox.check_api_key")
def test_run_quota_exceeded_captures_sentry_warning_and_exits_zero(mock_check):
    mock_check.side_effect = ValueError("xbox_quota_exceeded")
    with patch("scripts.xbox_health_check.sentry_sdk") as mock_sentry:
        code = run("valid-key")
    assert code == 0
    mock_sentry.capture_message.assert_called_once_with(
        "OpenXBL quota near limit", level="warning"
    )


@patch("scripts.xbox_health_check.xbox.check_api_key")
def test_run_api_unavailable_exits_zero_no_sentry(mock_check):
    mock_check.side_effect = ValueError("xbox_api_unavailable")
    with patch("scripts.xbox_health_check.sentry_sdk") as mock_sentry:
        code = run("valid-key")
    assert code == 0
    mock_sentry.capture_message.assert_not_called()
