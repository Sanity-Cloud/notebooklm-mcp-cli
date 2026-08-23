from __future__ import annotations

import json

from notebooklm_tools.mcp.diagnostics import CONTRACT_VERSION, EVENT_PREFIX, emit_diagnostic_event
from notebooklm_tools.mcp.tools._utils import error_result, service_error_result
from notebooklm_tools.services.errors import ServiceError, ValidationError


def _event(stderr: str) -> dict:
    line = stderr.strip()
    assert line.startswith(EVENT_PREFIX)
    return json.loads(line[len(EVENT_PREFIX) :])


def test_native_event_is_gated_and_secret_safe(monkeypatch, capsys) -> None:
    monkeypatch.delenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION", raising=False)
    assert emit_diagnostic_event(code="TEST", message="not supervised", operation="test") is False
    assert capsys.readouterr().err == ""

    monkeypatch.setenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION", CONTRACT_VERSION)
    assert (
        emit_diagnostic_event(
            code="NOTEBOOKLM_PROVIDER_ERROR",
            message="Bearer abc123secret should be hidden",
            operation="test_event",
            details={"cookies": "do-not-emit", "provider_code": 502},
        )
        is True
    )
    event = _event(capsys.readouterr().err)
    assert event["details"]["cookies"] == "[REDACTED]"
    assert event["details"]["provider_code"] == 502
    assert "abc123secret" not in event["message"]


def test_error_result_preserves_response_shape_and_emits_one_event(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION", CONTRACT_VERSION)

    result = error_result(
        "Notebook was unavailable", hint="Retry later", status="error", notebook_id="nb-1"
    )

    assert result == {
        "status": "error",
        "error": "Notebook was unavailable",
        "hint": "Retry later",
        "notebook_id": "nb-1",
    }
    event = _event(capsys.readouterr().err)
    assert event["code"] == "NOTEBOOKLM_MCP_ERROR_RESULT"
    assert event["kind"] == "tool_error_result"


def test_service_error_result_emits_typed_event_without_duplicate(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION", CONTRACT_VERSION)
    error = ValidationError(
        "bad value",
        user_message="Invalid notebook ID",
        hint="Check the ID",
        debug_code="invalid_notebook_id",
        category="validation",
        retryable=False,
    )

    result = service_error_result(error)

    assert result["status"] == "error"
    assert result["error"] == "Invalid notebook ID"
    assert result["hint"] == "Check the ID"
    lines = [line for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert len(lines) == 1
    event = _event(lines[0])
    assert event["code"] == "NOTEBOOKLM_VALIDATIONERROR"
    assert event["severity"] == "warning"
    assert event["details"]["debug_code"] == "invalid_notebook_id"


def test_service_error_result_marks_retryable_provider_failure(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION", CONTRACT_VERSION)
    error = ServiceError(
        "provider timeout",
        user_message="NotebookLM upstream timed out",
        category="provider",
        provider_code=504,
        retryable=True,
        suggested_action="retry",
    )

    service_error_result(error)

    event = _event(capsys.readouterr().err)
    assert event["code"] == "NOTEBOOKLM_SERVICEERROR"
    assert event["retryable"] is True
    assert event["details"]["provider_code"] == 504
    assert event["details"]["suggested_action"] == "retry"
