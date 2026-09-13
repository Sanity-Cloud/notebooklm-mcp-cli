"""Tests for profile-aware MCP usage reporting."""

import asyncio
from unittest.mock import MagicMock, patch

from notebooklm_tools.mcp.server import mcp
from notebooklm_tools.mcp.tools.usage import usage_get


def _usage_for(client):
    return {"windows": [], "tier": client.test_label}


def test_usage_get_accepts_explicit_profile():
    client = MagicMock(name="secondary")
    client.test_label = "secondary"
    with (
        patch("notebooklm_tools.mcp.tools.usage.create_profile_client", return_value=client) as create_profile_client,
        patch("notebooklm_tools.mcp.tools.usage.usage_service.get_usage", side_effect=_usage_for),
    ):
        result = usage_get(profile="secondary")

    assert result["status"] == "success"
    assert result["tier"] == "secondary"
    create_profile_client.assert_called_once_with("secondary")


def test_usage_get_without_profile_keeps_default_client_behavior():
    client = MagicMock(name="default")
    client.test_label = "default"
    with (
        patch("notebooklm_tools.mcp.tools.usage.get_client", return_value=client) as get_client,
        patch("notebooklm_tools.mcp.tools.usage.usage_service.get_usage", side_effect=_usage_for),
    ):
        result = usage_get()

    assert result["status"] == "success"
    assert result["tier"] == "default"
    get_client.assert_called_once_with()


def test_usage_get_keeps_explicit_profiles_isolated():
    clients = {"alpha": MagicMock(name="alpha"), "beta": MagicMock(name="beta")}
    clients["alpha"].test_label = "alpha"
    clients["beta"].test_label = "beta"
    with (
        patch(
            "notebooklm_tools.mcp.tools.usage.create_profile_client",
            side_effect=lambda profile: clients[profile],
        ) as create_profile_client,
        patch("notebooklm_tools.mcp.tools.usage.get_client") as get_default_client,
        patch("notebooklm_tools.mcp.tools.usage.usage_service.get_usage", side_effect=_usage_for),
    ):
        results = [usage_get(profile=name)["tier"] for name in ("alpha", "beta", "alpha")]

    assert results == ["alpha", "beta", "alpha"]
    assert [call.args[0] for call in create_profile_client.call_args_list] == ["alpha", "beta", "alpha"]
    get_default_client.assert_not_called()


def test_usage_get_missing_profile_returns_structured_error():
    with patch(
        "notebooklm_tools.mcp.tools.usage.create_profile_client",
        side_effect=ValueError("Profile 'missing' not found"),
    ):
        result = usage_get(profile="missing")

    assert result["status"] == "error"
    assert result["error"] == "Profile 'missing' not found"


def test_usage_get_schema_advertises_optional_profile():
    tool = asyncio.run(mcp.get_tool("usage_get"))

    assert tool is not None
    profile_schema = tool.parameters["properties"]["profile"]
    assert "profile" not in tool.parameters.get("required", [])
    assert {entry.get("type") for entry in profile_schema["anyOf"]} == {"string", "null"}
