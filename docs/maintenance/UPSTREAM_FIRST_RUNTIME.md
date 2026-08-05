# Upstream-first private runtime maintenance

## Branch contract

The runtime is maintained as three layers:

1. `origin/main`: unmodified upstream history.
2. `sanitycloud/upstreamable-stack-20260805`: generic changes intended for upstream review.
3. `sanitycloud/private-layered-20260805`: one private plugin-seam commit above the generic stack.

The authentication broker, Notion bridge, and ChatGPT bridge remain separate packages. Their implementation is not copied into the runtime repository.

## Current generic patch queue

| Order | Purpose | Integration commit |
|---:|---|---|
| 1 | Windows Claude profile fallback | `f3aea97` |
| 2 | Bounded source and artifact readiness polling | `49fba87` |
| 3 | Structured provider query errors | `be935d9` |
| 4 | Structured readiness-error serialization | `2bb6b25` |
| 5 | Configurable rate-limit retry ceiling | `49c05fd` |
| 6 | Conservative runtime capability reporting | `e71dc79` |

The private layer contains one commit named `feat(mcp): add optional private plugin seam`. Commit hashes may change after rebasing; the branch topology is authoritative.

## Update procedure

Run a non-mutating inspection first:

```powershell
pwsh -File .\scripts\rebase-private-runtime.ps1
```

Apply the update only from clean worktrees:

```powershell
pwsh -File .\scripts\rebase-private-runtime.ps1 -Apply
```

The script:

- fetches `origin`;
- refuses dirty worktrees;
- creates timestamped backup branches;
- rebases the generic stack onto `origin/main`;
- rebases the single private commit onto the updated stack;
- runs Ruff and the complete test suite for both layers.

A conflict stops the process without discarding state. Resolve or abort the active rebase before another attempt.

## Promotion gates

- **U1 — Upstream publication:** each generic branch must remain independently reviewable and validated before push or pull request creation.
- **P1 — Private pilot:** all three external plugins must register simultaneously with no duplicate or missing built-in tools.
- **A1 — Adoption:** replacement of the deployed vendor branch requires an explicit deployment decision and rollback receipt.

Never infer provider-side NotebookLM capabilities from an account plan label. `server_info` reports built-in MCP visibility and marks provider capabilities as unprobed unless a separate provider probe supplies evidence.

