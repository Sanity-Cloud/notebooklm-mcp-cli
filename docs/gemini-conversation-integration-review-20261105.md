# Gemini conversation discovery: integration security review and validation

**Date:** 2026-11-05
**Project:** SanityCloud NotebookLM MCP
**Basis:** existing commit `b6de9eb`, feature branch
`feat/gemini-conversation-shared-session-20261103`
**Classification:** EXPERIMENTAL. No public API contract. Feature flag OFF by default.

## Authorized scope

Review, harden, test and locally integrate a read-only Gemini
notebook-scoped conversation listing via the **existing** NotebookLM
authenticated Google session. Do not modify Google notebooks, publish an
upstream PR, or enable this experimental feature in the running service.

## Security review findings and disposition

| Issue | Severity | Disposition |
| --- | --- | --- |
| A caller could choose a different Gemini `/u/N/` account route while using a named NotebookLM profile | High | **Fixed:** require explicit per-profile JSON mapping `NOTEBOOKLM_GEMINI_ACCOUNT_BINDINGS`; reject absent/malformed/unbound settings, booleans, wrong indices, and unbound environment-only identities before network requests |
| Notebook UUID/source-overlap validation proves access to a shared notebook, not that Gemini and NotebookLM are signed in as the same human identity | High | **Partially mitigated:** explicit operator-verified profile-to-index binding required; source UUID overlap remains a second check; cannot cryptographically establish identity with private web RPC alone. Keep OFF until human account mapping is independently verified |
| Gemini `f.sid` token is carried in request URLs and may leak in HTTP diagnostic logs; temporary logger filters have incomplete concurrency coverage | High | **Fixed for expected built-in logging paths:** fail closed whenever `httpx` or `httpcore` INFO/DEBUG diagnostics are effective; retain URL redaction as defense in depth. External network tracing must remain disabled |
| Undocumented `MaZiqc` and `HcT8bb` response structures can change | Medium | Fail closed on changed frames or unknown notebook structure; require exact notebook reference and at least one native source UUID overlap; no automatic retries or account fallback |
| Gemini chat IDs are distinct from native NotebookLM conversation IDs | Medium | Keep `gemini_conversation_id` and `conversation_namespace=gemini`; no transcript claims, writes, or native history mutation |
| Sensitive titles in logs | Medium | Register via `unlogged_tool`, not generic response-serializing MCP decorator; sanitize raised transport errors |

## Verified results

- Feature flag disabled by default: `NOTEBOOKLM_ENABLE_GEMINI_CONVERSATIONS`
- Operator binding additionally required: `NOTEBOOKLM_GEMINI_ACCOUNT_BINDINGS`
- Local isolated live read-only tests with an ephemeral profile binding:
  - Notebook with 183 native sources: 175 source IDs matched, 8 Gemini conversations returned
  - Notebook with 237 native sources: 236 source IDs matched, 1 Gemini conversation returned
- Focused tests: 52 passed after hardening (including registration tests).
- Full suite in isolated temporary HOME and USERPROFILE:
  **2,646 passed, 42 skipped, 42 deselected**.
- Repository-wide Ruff lint and format checks passed (332 files formatted).
- `git diff --check` passed.
- No captured Google tokens or credentials written to source, tests, docs, or receipts.
- Prior source search remains available; upstream PR #391 is outside this scope.

## Deployment acceptance gate

1. Verify no competing Git/write owner and a clean checkout.
2. Fast-forward the existing active checkout from `feat/native-source-search-20261103`.
3. Leave the Gemini flag unset/0 in the runtime; do not establish a production
   profile-to-Gemini account binding.
4. Use the existing SanityCloud NotebookLM runner and bounded restart loop,
   rather than a new service mechanism.
5. Verify `GET /health`, new MCP tool visibility, disabled status,
   existing `source_search` and `server_info`.
6. Record exact post-deployment Git and runtime state, and any gaps honestly.

**Residual limitation:** This is shared Google browser-session reuse,
not an official OAuth integration or an authorized general-purpose Gemini API.
Further use requires explicit per-account mapping review and vendor-change
monitoring. No claim of independent second-human review is made.
