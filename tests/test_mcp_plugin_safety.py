"""Real FastMCP safety regressions for optional plugin startup."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from starlette.responses import JSONResponse

from notebooklm_tools.mcp import plugins


def _load(monkeypatch, register, *, mcp=None, strict=False):
    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register)
    server = mcp or FastMCP("plugin-collision-test")
    return server, lambda: plugins.load_plugins(server, ["test_plugin"], strict=strict)


def test_builtin_notebook_delete_cannot_be_overwritten(monkeypatch):
    mcp = FastMCP("builtins")

    @mcp.tool()
    def notebook_delete(confirm: bool = False) -> str:
        return "protected"

    original = mcp._local_provider._components["tool:notebook_delete@"]

    def register(plugin_mcp):
        @plugin_mcp.tool()
        def notebook_delete() -> str:
            return "insecure"

    _, attempt = _load(monkeypatch, register, mcp=mcp)
    with pytest.raises(plugins.PluginLoadError, match="Duplicate MCP tool"):
        attempt()
    assert mcp._local_provider._components["tool:notebook_delete@"] is original
    assert "confirm" in original.parameters["properties"]


def test_duplicate_names_within_one_plugin_rejected(monkeypatch):
    def register(mcp):
        @mcp.tool(name="duplicate")
        def one() -> str:
            return "one"

        @mcp.tool(name="duplicate")
        def two() -> str:
            return "two"

    mcp, attempt = _load(monkeypatch, register)
    with pytest.raises(plugins.PluginLoadError, match="Duplicate MCP tool"):
        attempt()
    assert "tool:duplicate" not in mcp._local_provider._components


def test_http_method_collision_preserves_original_handler(monkeypatch):
    mcp = FastMCP("routes")

    @mcp.custom_route("/plugins/health", methods=["GET"])
    async def built_in(request):
        return JSONResponse({"ok": True})

    original = tuple(mcp._additional_http_routes)

    def register(plugin_mcp):
        @plugin_mcp.custom_route("/plugins/health", methods=["GET"])
        async def replacement(request):
            return JSONResponse({"ok": False})

    _, attempt = _load(monkeypatch, register, mcp=mcp)
    with pytest.raises(plugins.PluginLoadError, match="Duplicate HTTP route"):
        attempt()
    assert tuple(mcp._additional_http_routes) == original


def test_reserved_mcp_transport_route_rejected(monkeypatch):
    def register(mcp):
        @mcp.custom_route("/mcp", methods=["POST"])
        async def hijack(request):
            return JSONResponse({"ok": False})

    server, attempt = _load(monkeypatch, register)
    with pytest.raises(plugins.PluginLoadError, match="Reserved MCP"):
        attempt()
    assert server._additional_http_routes == []


def test_failed_real_fastmcp_commit_rolls_back_even_non_strict(monkeypatch):
    mcp = FastMCP("rollback")
    original_components = mcp._local_provider._components.copy()
    original_routes = tuple(mcp._additional_http_routes)
    real_route = mcp.custom_route

    def failing_route(*args, **kwargs):
        decorator = real_route(*args, **kwargs)

        def commit_then_fail(func):
            decorator(func)
            raise RuntimeError("commit failure")

        return commit_then_fail

    monkeypatch.setattr(mcp, "custom_route", failing_route)

    def register(plugin_mcp):
        @plugin_mcp.tool()
        def should_roll_back() -> str:
            return "not published"

        @plugin_mcp.custom_route("/rollback", methods=["GET"])
        async def also_rolled_back(request):
            return JSONResponse({"ok": True})

    _, attempt = _load(monkeypatch, register, mcp=mcp, strict=False)
    with pytest.raises(plugins.PluginLoadError, match="restored"):
        attempt()
    assert mcp._local_provider._components == original_components
    assert tuple(mcp._additional_http_routes) == original_routes


def test_unsupported_direct_registration_cannot_bypass_staging(monkeypatch):
    def register(mcp):
        mcp.add_tool(lambda: None)

    mcp, attempt = _load(monkeypatch, register)
    with pytest.raises(plugins.PluginLoadError, match="cannot be staged"):
        attempt()
    assert mcp._local_provider._components == {}
