# Native NotebookLM indexed-source retrieval (`ASU5Oe`)

**Status:** EXPERIMENTAL, implemented and live read-only verified, not deployed.
**Repository branch:** `feat/native-source-search-20261103`.
**Authentication:** existing NotebookLM session; no Gemini/Opal token reuse.

## Why this capability exists

`notebook_get` returns the notebook's source inventory, and
`source_get_content` reads a complete source. The existing notebook Q&A tool
generates an answer. The new `source_search` returns bounded, source-attributed
passages relevant to a query, without requiring a generated answer or returning
entire documents.

The private NotebookLM `ASU5Oe` RPC was successfully exercised on November 3,
2026 with the active NotebookLM identity. The call returned grouped native
source UUIDs and passage text. The format is undocumented and could change.

## Invocation

The MCP tool is registered in the `sources_read` group but is disabled unless
the MCP process has `NOTEBOOKLM_ENABLE_NATIVE_SOURCE_SEARCH=1`. Enable only after
checking current identity, governance rules, and deployment ownership. For
accounts requiring visible login, retain
`NOTEBOOKLM_DISABLE_HEADLESS_REFRESH=1`.

```text
source_search(
  notebook_id="<native NotebookLM notebook UUID>",
  query="agent orchestration",
  source_ids=null,
  max_results=8,
  snippet_chars=900
)
```

- `source_ids`: optional list of 1–10 native source UUIDs. Each is checked
  against the selected notebook before retrieval; foreign/unknown IDs fail.
- `max_results`: 1–20, defaults to 8.
- `snippet_chars`: 1–1800, defaults to 900.
- Total excerpt text is capped at 12,000 characters per response. Query length
  is capped at 1,000 characters.
- `query` is not reflected in response metadata. Results include native source
  UUID, current title, returned passage ordinal, bounded excerpt, and
  truncation flag.
- Results are diversified round-robin across returned source groups. **No
  global ranking score is exposed by this implementation.** Native ordering
  within each group is preserved.

## Verified request structure

```text
rpc: ASU5Oe
method: existing NotebookLM batchexecute client
notebook path: /notebook/{notebook_id}

unfiltered: [notebook_id, query, null, [1]]
filtered:   [notebook_id, query, null, [1], [[[source_id_1, source_id_2]]]]
```

Observed response: one outer list containing source groups. Each source group
contains a native UUID and multiple passage records. Each passage record has a
strictly nested text field plus positional fields whose semantics are not
assumed by the adapter.

**Do not infer that the output is a complete notebook inventory or a stable
global ranking.** The RPC signature and response shape are undocumented.

## Verification

- Unfiltered live test: 8 returned passages from 8 distinct native sources;
  query-redaction and per-excerpt limit checked.
- Two-source live filter: 8 passages from 2 selected sources, with no foreign
  source identifiers.
- Prior structural probe: 26 source UUIDs, 103 passages, and all 26 UUIDs
  matched the notebook's native source list.
- Test suite covers malformed data, input limits, output size caps,
  request-filter shaping, cross-notebook protection, deterministic source
  diversification, and debug logging suppression.

## Privacy, authentication and operational boundaries

This tool uses the existing NotebookLM `get_client` and `_call_rpc`; it does not
copy Google tokens, read HARs, or call Gemini/Opal directly. It is registered
outside the general `logged_tool` wrapper because that wrapper serializes MCP
results in debug mode. The `ASU5Oe` RPC also suppresses the core transport's
debug serialization of query and retrieved passages. Normal HTTP transport and
any externally configured diagnostics still require separate operational review.

It does not write notebook content, create artifacts, or modify auth state
deliberately. Any startup/login recovery remains governed by existing NLM
session policy, not this operation.

## Other experimental branches

`feat/gemini-maziqc-readonly-20261103` at `dbbd3d4` was kept separate.
The evidence no longer supports treating `MaZiqc` as a complete native source
list; it may represent notebook-scoped Gemini conversation metadata.
**Do not merge or deploy that adapter as source-listing functionality.**

The newer Gemini `HcT8bb` and `ko3zcd` responses contained native-source
titles but not confirmed native-source ID mappings or passage retrieval, and
do not yet establish standalone authorization or a production dependency.

## Deployment gate

Only after code review, full regression, identity check, and read-only MCP
smoke validation should the feature branch be considered for merging and
deploying through the existing SanityCloud process. Do not add a second auth
broker, auto-replay captured tokens, or change production services as part of
source retrieval development.
