"""Tests for optional MCP plugin loading."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from notebooklm_tools.mcp import plugins


class FakeMCP:
    def __init__(self) -> None:
        self.tools: list[str] = []
        self.routes: list[tuple[str, tuple[str, ...]]] = []
        self.tool_options: list[dict] = []

    def tool(self, **kwargs):
        def decorator(func):
            self.tools.append(func.__name__)
            self.tool_options.append(kwargs)
            return func

        return decorator

    def custom_route(self, path: str, methods: list[str], **kwargs):
        def decorator(func):
            self.routes.append((path, tuple(methods)))
            return func

        return decorator


@dataclass
class FakeEntryPoint:
    name: str
    loaded: Any

    def load(self) -> Any:
        return self.loaded


def test_load_plugins_disabled_by_default(monkeypatch):
    monkeypatch.delenv(plugins.PLUGIN_ENV_VAR, raising=False)
    monkeypatch.delenv(plugins.PLUGIN_AUTOLOAD_ENV_VAR, raising=False)

    result = plugins.load_plugins(FakeMCP())

    assert result == []


def test_load_module_register_function(monkeypatch, tmp_path):
    module_path = tmp_path / "sample_plugin.py"
    module_path.write_text(
        "def register(mcp):\n"
        "    @mcp.tool()\n"
        "    def sample_plugin_status():\n"
        "        return {'status': 'success'}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(plugins.PLUGIN_ENV_VAR, "sample_plugin")
    mcp = FakeMCP()

    result = plugins.load_plugins(mcp)

    assert result == [{"name": "sample_plugin", "status": "loaded"}]
    assert mcp.tools == ["sample_plugin_status"]


def test_load_module_attribute_function(monkeypatch, tmp_path):
    module_path = tmp_path / "attribute_plugin.py"
    module_path.write_text(
        "def install(mcp):\n"
        "    @mcp.custom_route('/plugin-health', methods=['GET'])\n"
        "    async def plugin_health(request):\n"
        "        return None\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    mcp = FakeMCP()

    result = plugins.load_plugins(mcp, ["attribute_plugin:install"])

    assert result == [{"name": "attribute_plugin:install", "status": "loaded"}]
    assert mcp.routes == [("/plugin-health", ("GET",))]


def test_missing_plugin_is_strict_by_default():
    with pytest.raises(plugins.PluginLoadError, match="missing_plugin"):
        plugins.load_plugins(FakeMCP(), ["missing_plugin"])


def test_missing_plugin_can_be_non_strict():
    result = plugins.load_plugins(FakeMCP(), ["missing_plugin"], strict=False)

    assert result[0]["name"] == "missing_plugin"
    assert result[0]["status"] == "error"
    assert "No module named" in result[0]["error"]


def test_entry_point_plugin_loads_by_name(monkeypatch):
    def register(mcp):
        @mcp.tool()
        def entry_point_tool():
            return {"status": "success"}

    monkeypatch.setattr(
        plugins,
        "_entry_points",
        lambda: [FakeEntryPoint("sample-entry", register)],
    )
    mcp = FakeMCP()

    result = plugins.load_plugins(mcp, ["sample-entry"])

    assert result == [{"name": "sample-entry", "status": "loaded"}]
    assert mcp.tools == ["entry_point_tool"]


def test_autoload_entry_points(monkeypatch):
    def register(mcp):
        mcp.loaded = True

    monkeypatch.setenv(plugins.PLUGIN_AUTOLOAD_ENV_VAR, "true")
    monkeypatch.delenv(plugins.PLUGIN_ENV_VAR, raising=False)
    monkeypatch.setattr(
        plugins,
        "_entry_points",
        lambda: [FakeEntryPoint("auto-entry", register)],
    )
    mcp = SimpleNamespace(loaded=False)

    result = plugins.load_plugins(mcp)

    assert result == [{"name": "auto-entry", "status": "loaded"}]
    assert mcp.loaded is True


def test_plugin_failure_discards_staged_tool(monkeypatch):
    def register_then_fail(mcp):
        @mcp.tool()
        def should_not_appear():
            return 1

        raise RuntimeError("intentional failure")

    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register_then_fail)
    mcp = FakeMCP()
    result = plugins.load_plugins(mcp, ["broken_plugin"], strict=False)
    assert result[0]["status"] == "error"
    assert mcp.tools == []


def test_plugin_failure_discards_staged_route(monkeypatch):
    def register_then_fail(mcp):
        @mcp.custom_route("/never-visible", methods=["GET"])
        async def should_not_appear(request):
            return None

        raise RuntimeError("intentional failure")

    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register_then_fail)
    mcp = FakeMCP()
    result = plugins.load_plugins(mcp, ["broken_route"], strict=False)
    assert result[0]["status"] == "error"
    assert mcp.routes == []


def test_plugin_duplicate_is_loaded_once_and_metadata_survives(monkeypatch):
    def register(mcp):
        @mcp.tool(meta={"openai/fileParams": ["file"]})
        def bridge_upload(file: str):
            return file

    monkeypatch.setattr(plugins, "_load_module_plugin", lambda _: register)
    mcp = FakeMCP()
    result = plugins.load_plugins(mcp, ["bridge", "bridge"])
    assert [item["status"] for item in result] == ["loaded", "skipped"]
    assert mcp.tools == ["bridge_upload"]
    assert mcp.tool_options == [{"meta": {"openai/fileParams": ["file"]}}]
