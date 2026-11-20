# NotebookLM MCP hardening, 2026-11-20

This fork retains the ChatGPT binary file bridge, Notion bridge, and auth broker.
This change set strengthens the core MCP boundary without changing local CLI
file-access behavior or the bridge's independent tokenized transport.

## MCP local-file access policy

`source_add(source_type="file")` now requires `NOTEBOOKLM_ALLOWED_FILE_DIRS`
to be configured in the NotebookLM MCP server process. The value is a
platform-path-separated set of trusted directory roots (`;` on Windows).
A path outside those roots is denied; symlinks are resolved before admission.
An unset or empty configuration denies MCP file uploads, not CLI uploads.

Example for a managed Windows instance:

```powershell
$env:NOTEBOOKLM_ALLOWED_FILE_DIRS = 'X:\MCP\staging;X:\Code\sanity-cloud-ai-portal\tmp\notebooklm-chatgpt-bridge\inbound'
```

The supervisor must set the environment variable *before* starting MCP.
Do not edit the generated `notebooklm-mcp.runner.ps1`: it is overwritten.
The ChatGPT plugin's separate incoming file-transfer route keeps its own
checks and is not automatically governed by this core MCP path guard.

## Payload-safe diagnostics

Core MCP `logged_tool` decorators now report operation, fixed outcome class,
and wall-clock duration. They no longer serialize arguments or return bodies,
even with DEBUG enabled. The privacy-sensitive `unlogged_tool` remains intact.

## Plugin loading

Plugin registration through `mcp.tool()` and `mcp.custom_route()` is staged
until the registration callback finishes. Duplicate plugin specs are skipped.
Third-party plugins that mutate other MCP internals or perform side effects
inside their callback remain outside the supported transactional guarantee.
Commit-time registry failures can still partially register tools; supporting
more APIs requires a versioned plugin SDK and registry preflight checks.

## Memory and follow-on work

Per-element interactive-report locks now use a weak-value registry so inactive
IDs do not accumulate permanently. Live requests still hold strong references
while locking an element. The broader persistent-job and request-scoped
profile refactors are **not included** in this security-focused change.

Acceptance requires Ruff, the full pytest suite, the three custom plugins
present after a managed restart, a valid MCP POST health check, and a matching
runtime version. Do not claim production deployment from passing tests alone.
