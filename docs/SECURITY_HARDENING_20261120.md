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
$env:NOTEBOOKLM_ALLOWED_FILE_DIRS = 'X:\Code\sanity-cloud-ai-portal\tmp\notebooklm-notion-bridge;X:\Code\sanity-cloud-ai-portal\tmp\notebooklm-chatgpt-bridge\inbound'
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
The follow-up registration preflight now rejects built-in and plugin tool-name
collisions, overlapping HTTP method/path combinations, and reserved transport
paths before mutating the supported FastMCP 4.x registries. Supported tool and
route registry mutations are restored if a commit raises. Unsafe registration
errors always abort startup, even with `NOTEBOOKLM_MCP_PLUGIN_STRICT=false`.

This is not a sandbox or a generic atomic plugin API. Plugins are trusted Python
modules: arbitrary object changes or side effects inside registration callbacks
cannot be rolled back. Other registration APIs, unknown methods and direct facade attribute writes
are deliberately rejected. Unrecognized FastMCP registry shapes, including
malformed route tuples, cannot fall through the recoverable strict=false loader
path. This fix addresses the isolated AiGentAI Copilot review P1 finding.
Rollback restores captured top-level registry containers, not nested object
state or arbitrary plugin side effects. Full FastMCP/ASGI atomicity is not
claimed. Versioned SDK support, file-open replacement races and adversarial
isolation remain separate design work. Real FastMCP tests cover built-in tool
schema preservation, route collisions, rollback on a failed commit, malformed
registry inspection and strict=false fail-closed behavior.

## Memory and follow-on work

Per-element interactive-report locks now use a weak-value registry so inactive
IDs do not accumulate permanently. Live requests still hold strong references
while locking an element. The broader persistent-job and request-scoped
profile refactors are **not included** in this security-focused change.

Acceptance requires Ruff, the full pytest suite, the three custom plugins
present after a managed restart, a valid MCP POST health check, and a matching
runtime version. Do not claim production deployment from passing tests alone.
