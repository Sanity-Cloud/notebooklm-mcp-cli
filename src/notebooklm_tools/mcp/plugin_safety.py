"""Collision preflight and startup-only rollback for optional MCP registrations.

Only FastMCP 4.x tool and custom_route decorator registrations are supported.
A plugin is trusted Python code, not a sandbox; arbitrary side effects cannot be
reverted. We fail startup instead of serving a partially installed plugin.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_RESERVED_HTTP_PATHS = frozenset({"/mcp", "/sse", "/messages", "/health", "/healthz"})


class PluginRegistrationError(RuntimeError):
    """A plugin registration was rejected or could not finish safely."""


def _tool_names(mcp: Any) -> set[str]:
    provider = getattr(mcp, "_local_provider", None)
    if provider is not None:
        components = getattr(provider, "_components", None)
        if not isinstance(components, dict):
            raise PluginRegistrationError("Unable to inspect FastMCP tool registry")
        return {
            str(component.name)
            for key, component in components.items()
            if str(key).startswith("tool:") and getattr(component, "name", None)
        }
    tools = getattr(mcp, "tools", None)
    if isinstance(tools, list):
        return {str(name) for name in tools}
    raise PluginRegistrationError("Unknown MCP tool registry; rejecting plugin")


def _route_records(mcp: Any) -> list[tuple[str, set[str], str | None]]:
    routes = getattr(mcp, "_additional_http_routes", None)
    if routes is None:
        routes = getattr(mcp, "routes", None)
    if not isinstance(routes, list):
        raise PluginRegistrationError("Unknown MCP route registry; rejecting plugin")
    records = []
    for route in routes:
        if isinstance(route, tuple):
            path, methods = route
            name = None
        else:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            name = getattr(route, "name", None)
        if not isinstance(path, str) or methods is None:
            raise PluginRegistrationError("Unable to inspect existing HTTP route")
        records.append((path, {str(m).upper() for m in methods}, name))
    return records


def validate_registrations(
    mcp: Any,
    registrations: Sequence[tuple[str, tuple[Any, ...], dict[str, Any], Any]],
) -> None:
    """Reject duplicate tool names and overlapping HTTP paths/methods."""
    if not registrations:
        return
    tools = _tool_names(mcp)
    routes = _route_records(mcp)
    route_names = {name for _, _, name in routes if name is not None}
    for kind, args, options, func in registrations:
        if kind == "tool":
            explicit = options.get("name")
            if explicit is None and args and isinstance(args[0], str):
                explicit = args[0]
            name = explicit or getattr(func, "__name__", None)
            if not isinstance(name, str) or not name.strip():
                raise PluginRegistrationError("Plugin tool must have a stable name")
            if name in tools:
                raise PluginRegistrationError(
                    f"Duplicate MCP tool name {name!r}; built-in or plugin tool preserved"
                )
            tools.add(name)
        elif kind == "custom_route":
            path = args[0] if args else options.get("path")
            methods = args[1] if len(args) > 1 else options.get("methods")
            name = options.get("name")
            if not isinstance(path, str) or not path.startswith("/"):
                raise PluginRegistrationError("Plugin HTTP route needs an absolute path")
            if not isinstance(methods, (list, tuple, set)) or not methods:
                raise PluginRegistrationError("Plugin HTTP route must list methods")
            normalized = {str(method).upper() for method in methods}
            if path in _RESERVED_HTTP_PATHS or path.startswith("/mcp/"):
                raise PluginRegistrationError(f"Reserved MCP HTTP route: {path}")
            if name is not None and name in route_names:
                raise PluginRegistrationError(f"Duplicate HTTP route name: {name}")
            if any(
                path == old_path and normalized & old_methods for old_path, old_methods, _ in routes
            ):
                raise PluginRegistrationError(
                    f"Duplicate HTTP route/method at {path}: {sorted(normalized)}"
                )
            routes.append((path, normalized, name))
            if name is not None:
                route_names.add(name)
        else:
            raise PluginRegistrationError(f"Unsupported registration method: {kind}")


def _capture_mutable_registries(mcp: Any) -> list[tuple[Any, str, Any]]:
    """Capture only registries modified by supported decorator registrations."""
    provider = getattr(mcp, "_local_provider", None)
    candidates = (
        (provider, "_components"),
        (mcp, "_additional_http_routes"),
        (mcp, "tools"),
        (mcp, "tool_options"),
        (mcp, "routes"),
    )
    snapshots = []
    for owner, attribute in candidates:
        if owner is None:
            continue
        registry = getattr(owner, attribute, None)
        if isinstance(registry, dict):
            snapshots.append((registry, "dict", registry.copy()))
        elif isinstance(registry, list):
            snapshots.append((registry, "list", registry.copy()))
    return snapshots


def publish_registrations(
    mcp: Any,
    registrations: Sequence[tuple[str, tuple[Any, ...], dict[str, Any], Any]],
) -> None:
    """Preflight the staged changes, then roll back supported state on failure."""
    validate_registrations(mcp, registrations)
    snapshots = _capture_mutable_registries(mcp)
    try:
        for kind, args, options, func in registrations:
            getattr(mcp, kind)(*args, **options)(func)
    except Exception as exc:
        for registry, kind, snapshot in reversed(snapshots):
            registry.clear()
            if kind == "dict":
                registry.update(snapshot)
            else:
                registry.extend(snapshot)
        raise PluginRegistrationError(
            "Plugin registration failed; restored tool/route registries and aborted startup"
        ) from exc
