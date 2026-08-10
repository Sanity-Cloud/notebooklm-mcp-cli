from typer.testing import CliRunner

from notebooklm_tools.cli.main import app


class SavingAuthManager:
    save_calls: list[dict] = []

    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.profile_dir = f"/tmp/{profile_name}"

    def save_profile(self, **kwargs):
        self.__class__.save_calls.append(kwargs)


def test_external_cdp_login_leaves_browser_lifecycle_to_caller(monkeypatch):
    SavingAuthManager.save_calls = []
    close_calls: list[tuple[str, str]] = []

    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", SavingAuthManager)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_browser_display_name", lambda: "Chrome")
    monkeypatch.setattr(
        "notebooklm_tools.utils.cdp.extract_cookies_via_existing_cdp",
        lambda **_kwargs: {
            "cookies": {"SID": "sid"},
            "csrf_token": "csrf",
            "session_id": "session",
            "email": "user@example.com",
            "build_label": "build",
            "base_host": "notebooklm.google.com",
        },
    )
    monkeypatch.setattr(
        "notebooklm_tools.utils.cdp.close_profile_owned_cdp_browser",
        lambda cdp_url, profile: close_calls.append((cdp_url, profile)) or True,
    )

    result = CliRunner().invoke(
        app,
        [
            "login",
            "--profile",
            "KS",
            "--force",
            "--provider",
            "openclaw",
            "--cdp-url",
            "http://127.0.0.1:9227",
        ],
    )

    assert result.exit_code == 0
    assert close_calls == []
    assert SavingAuthManager.save_calls
    assert "Closing managed Chrome profile 'KS'" not in result.output
