"""SanityCloud base URL compatibility and validation tests."""

from __future__ import annotations

import pytest

from notebooklm_tools.utils.config import get_base_url


@pytest.mark.parametrize(
    "url",
    [
        "https://notebook.google.com",
        "https://notebook.google.com/",
        "https://notebooklm.google.com",
        "https://notebooklm.cloud.google.com",
    ],
)
def test_get_base_url_accepts_exact_supported_https_hosts(monkeypatch, url):
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", url)

    assert get_base_url() == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://notebook.google.com",
        "https://evil.example",
        "https://notebook.google.com.evil.example",
        "https://subdomain.notebook.google.com",
    ],
)
def test_get_base_url_rejects_insecure_or_unapproved_hosts(monkeypatch, url):
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", url)

    with pytest.raises(ValueError, match="must use https and one of"):
        get_base_url()
