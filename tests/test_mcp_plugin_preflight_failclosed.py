"""Fail-closed FastMCP plugin registration under unexpected registry shapes."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from starlette.responses import JSONResponse

from notebooklm_tools.mcp import plugins


def _staged_route(mcp):
    @mcp.custom_route("/new-plugin-route", methods=["GET"])
    async def new_route(request):
        return JSONResponse({"ok": True})


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "route",
    [
        ("/existing", {"GET"}, "three-fields"),
        ("/existing",),
        ("/existing", None),
        ("/existing", "GET"),
        ("/existing", [""]),
    ],
)
def test_malformed_existing_route_is_fatal_even_non_strict(monkeypatch, strict, route):
    mcp = FastMCP("malformed-existing-route")
    mcp._additional_http_routes.append(route)
    original_route = mcp._additional_http_routes[0]
    original_components = mcp._local_provider._components.copy()
    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: _staged_route)

    with pytest.raises(plugins.PluginLoadError, match="Unsafe registration"):
        plugins.load_plugins(mcp, ["synthetic-unsafe-plugin"], strict=strict)

    assert mcp._additional_http_routes == [original_route]
    assert mcp._local_provider._components == original_components


@pytest.mark.parametrize("strict", [False, True])
def test_unexpected_existing_route_property_exception_fails_closed(monkeypatch, strict):
    class IncompatibleRoute:
        @property
        def path(self):
            raise ValueError("new upstream route object shape")

    mcp = FastMCP("unknown-existing-route")
    original_route = IncompatibleRoute()
    mcp._additional_http_routes.append(original_route)
    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: _staged_route)

    with pytest.raises(plugins.PluginLoadError, match="Unsafe registration"):
        plugins.load_plugins(mcp, ["synthetic-unsafe-plugin"], strict=strict)
    assert mcp._additional_http_routes == [original_route]


@pytest.mark.parametrize("strict", [False, True])
def test_staged_proxy_rejects_unknown_mutation_before_it_happens(monkeypatch, strict):
    mcp = FastMCP("proxy-no-mutation")
    previous_name = mcp.name

    def register(proxy):
        proxy.name = "injected"

    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register)
    with pytest.raises(plugins.PluginLoadError, match="cannot be staged"):
        plugins.load_plugins(mcp, ["synthetic-unsafe-plugin"], strict=strict)
    assert mcp.name == previous_name


@pytest.mark.parametrize("strict", [False, True])
def test_staged_proxy_rejects_unknown_callable_access(monkeypatch, strict):
    mcp = FastMCP("proxy-no-unexpected-methods")

    def register(proxy):
        proxy.get_tools()

    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register)
    with pytest.raises(plugins.PluginLoadError, match="cannot be staged"):
        plugins.load_plugins(mcp, ["synthetic-unsafe-plugin"], strict=strict)
    assert mcp._local_provider._components == {}
