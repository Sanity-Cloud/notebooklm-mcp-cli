"""MCP debug logs must never include notebook payloads or user queries."""

import logging

import pytest

from notebooklm_tools.mcp.tools import _utils


def test_sync_tool_debug_logging_is_metadata_only(caplog, monkeypatch):
    monkeypatch.setattr(_utils, "maybe_attach_mcp_notice", lambda _: None)
    monkeypatch.setattr(_utils, "maybe_attach_active_profile_note", lambda *_: None)
    caplog.set_level(logging.DEBUG, logger="notebooklm_tools.mcp")
    initial_count = len(_utils._tool_registry)
    try:

        @_utils.logged_tool()
        def private_source(source_text: str):
            return {"status": "success", "content": "PRIVATE_SOURCE_BODY"}

        assert private_source("CONFIDENTIAL_QUESTION")["content"] == "PRIVATE_SOURCE_BODY"
    finally:
        del _utils._tool_registry[initial_count:]
    assert "MCP Request: private_source" in caplog.text
    assert "outcome=completed" in caplog.text
    assert "CONFIDENTIAL_QUESTION" not in caplog.text
    assert "PRIVATE_SOURCE_BODY" not in caplog.text


@pytest.mark.asyncio
async def test_async_tool_debug_logging_is_metadata_only(caplog, monkeypatch):
    monkeypatch.setattr(_utils, "maybe_attach_mcp_notice", lambda _: None)
    monkeypatch.setattr(_utils, "maybe_attach_active_profile_note", lambda *_: None)
    caplog.set_level(logging.DEBUG, logger="notebooklm_tools.mcp")
    initial_count = len(_utils._tool_registry)
    try:

        @_utils.logged_tool()
        async def private_chat(prompt: str):
            return {"status": "error", "error": "PRIVATE_RESPONSE"}

        assert (await private_chat("PRIVATE_PROMPT"))["status"] == "error"
    finally:
        del _utils._tool_registry[initial_count:]
    assert "outcome=error" in caplog.text
    assert "PRIVATE_PROMPT" not in caplog.text
    assert "PRIVATE_RESPONSE" not in caplog.text
