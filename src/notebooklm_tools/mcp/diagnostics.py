"""Portable SanityCloud diagnostic events for NotebookLM MCP failures."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from typing import Any

CONTRACT_VERSION = "sanitycloud.diagnostic.v1"
EVENT_PREFIX = "SANITYCLOUD_DIAGNOSTIC_EVENT "
_SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|cookie|authorization|api[_-]?key|credential|request_body)",
    re.IGNORECASE,
)
_TEXT_PATTERNS = (
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:token|password|secret|cookie|authorization|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
)


def _safe_text(value: Any) -> str:
    text = str(value or "")
    for pattern in _TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:2000]


def _safe(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if key and _SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if depth >= 6:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key)[:120]: _safe(item_value, key=str(item_key), depth=depth + 1)
            for item_key, item_value in list(value.items())[:80]
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(item, depth=depth + 1) for item in list(value)[:80]]
    return _safe_text(value)


def emit_diagnostic_event(
    *,
    code: str,
    message: str,
    operation: str,
    category: str = "notebooklm_mcp",
    severity: str = "error",
    kind: str = "error",
    retryable: bool = False,
    details: Mapping[str, Any] | None = None,
    evidence: list[Any] | None = None,
    parent_record_id: str | None = None,
    project_id: str | None = None,
    lane_id: str | None = None,
    decision_id: str | None = None,
) -> bool:
    """Emit one supervisor-consumable line; never alter the MCP result path."""

    if os.getenv("SANITYCLOUD_DIAGNOSTIC_CONTRACT_VERSION") != CONTRACT_VERSION:
        return False
    payload = {
        "component_id": "notebooklm",
        "code": str(code or "NOTEBOOKLM_MCP_ERROR").upper()[:160],
        "message": _safe_text(message or "NotebookLM MCP error."),
        "operation": str(operation or "mcp_tool")[:240],
        "category": str(category or "notebooklm_mcp")[:120],
        "severity": str(severity or "error")[:32],
        "kind": str(kind or "error")[:120],
        "retryable": bool(retryable),
        "source": "notebooklm_mcp_runtime",
        "parent_record_id": parent_record_id,
        "project_id": project_id,
        "lane_id": lane_id,
        "decision_id": decision_id,
        "details": _safe(dict(details or {})),
        "evidence": _safe(list(evidence or [])),
    }
    try:
        sys.stderr.write(EVENT_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stderr.flush()
        return True
    except Exception:  # pragma: no cover - diagnostics must never mask the tool result
        return False
