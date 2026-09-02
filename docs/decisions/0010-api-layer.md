# ADR 0010 — The API layer

**Status:** accepted
**Scope:** `pramaan/api/`

## What was built

A FastAPI service exposing case management, evidence and clip
bookkeeping, examiner findings, the composed timeline, audit-ledger
integrity verification, both report documents
([ADR 0008](0008-report-certificate.md),
[ADR 0009](0009-report-case-report.md)), and unsigned SEF export
([ADR 0007](0007-export-sef-format.md)) as one coherent HTTP interface.
`pramaan.api.app.create_app(workspace_root)` is the one entry point: it
builds a `CaseWorkspace` rooted at the given directory and mounts every
route onto a fresh `FastAPI` app. This layer adds no forensic logic of
its own — every route is a thin translation from an HTTP request to a
call against `pramaan.case`, `pramaan.timeline`, `pramaan.report`, or
`pramaan.export`, all of which were already implemented and tested
before this layer existed.

## Design decision: cases are addressed by ID, not by path — enforced structurally

`pramaan.case.store.Case` is deliberately path-based; it is meant to be
exactly as portable as any other SQLite file, and knows nothing about a
"workspace." An HTTP API cannot accept a client-supplied filesystem path
as a case identifier — that is a real path-traversal vector, not a
theoretical one. `CaseWorkspace` is the addressing scheme built
specifically for this layer: one flat directory, one `<case_id>.case`
file per case, and a case-ID format (`_CASE_ID_PATTERN`) that makes
escaping the workspace directory structurally impossible rather than
merely checked for — no `/`, no leading `.` (so it can never resolve to
`.` or `..`), no leading `-`. A parametrized test
(`test_case_id_cannot_escape_the_workspace_directory`) confirms this
directly rather than trusting the regex by inspection alone.

## Design decision: signing is explicitly out of scope for the export endpoint, not silently dropped

`build_sef_bundle` accepts an `Ed25519PrivateKey` to produce a signed
bundle, but there is no key-management endpoint in this layer to hold or
reference one safely over HTTP yet. Rather than either building a
half-considered signing endpoint under time pressure or silently
omitting signing without saying so, `POST /cases/{case_id}/export`
documents in its own module docstring that it builds unsigned bundles
only — every hash, ledger-chain check, and manifest-schema guarantee
`pramaan.export` provides still applies, and a caller needing a signed
bundle uses `pramaan.export.sef` directly with their own key material
until a dedicated signing endpoint exists. Stating a real boundary
honestly is not the same thing as a placeholder feature.

## Design decision: report and export endpoints return bytes, never a path

`generate_certificate_pdf`, `generate_case_report_pdf`, and
`build_sef_bundle` all refuse to overwrite an existing `dest_path` —
correct for a caller writing into a permanent location, irrelevant to an
HTTP response. Each of these three routes builds into a fresh
`tempfile.TemporaryDirectory()`, reads the result back as bytes, and
returns it directly as the response body with the right media type and
a `Content-Disposition` filename. Nothing a report or export request
generates is left on disk once the response is sent — the workspace
directory holds case files only, never generated artifacts.

## Design decision: response schemas validate directly from the existing dataclasses

Every response model (`CaseInfoResponse`, `EvidenceItemResponse`,
`ClipResponse`, `FindingResponse`, `SegmentResponse`,
`ChainVerificationResponse`) sets
`model_config = ConfigDict(from_attributes=True)` and is constructed
with `Model.model_validate(dataclass_instance)` directly against the
frozen dataclasses `pramaan.case.store` and `pramaan.timeline.model`
already return. This layer re-declares their shape for the OpenAPI
schema and JSON serialization; it does not re-implement or duplicate the
logic that produces them.

## A real per-request resource-management fix, caught before it shipped

The first version of the `get_case` dependency opened a `Case` (and
therefore a SQLite connection) and returned it directly. Nothing ever
closed that connection once the request finished — every request would
leak one. Fixed by making `get_case` a generator dependency: it opens
the case, `yield`s it for the route to use, and closes it in a `finally`
block that runs after the response is built, regardless of whether the
route raised. FastAPI runs generator-dependency teardown this way by
design; the fix is using that mechanism rather than a plain return.

## A real ruff finding: FastAPI's own recommended pattern trips flake8-bugbear's B008

Every route that depends on `get_case` (and `get_workspace`) writes
`case: Case = Depends(get_case)` — FastAPI's own documented pattern for
per-request dependency injection. `ruff`'s B008 rule (no function calls
in argument defaults) flags this as a case of the classic mutable-
default-argument footgun, which it structurally isn't: FastAPI calls
`Depends`'s target itself, fresh, on every request. Ruff's own
documented fix for exactly this false positive is
`[tool.ruff.lint.flake8-bugbear] extend-immutable-calls`, naming the
specific callables (`fastapi.Depends`, `Query`, `Path`, `Body`) that are
safe in this position — added to `pyproject.toml` as a targeted
carve-out, not a suppression of B008 anywhere else in the codebase.

## What review caught as genuinely reachable, not padding for coverage

- `CaseWorkspace.open_case` originally wrapped `Case(path)` in a
  `try/except CaseError`, but `Case`'s plain constructor only raises
  `CaseError` when the path doesn't exist — a condition `open_case`
  already checks and raises its own `WorkspaceError` for beforehand.
  The `except` branch was genuinely unreachable, not a real safety net;
  removed rather than padded with a contrived test, matching how earlier
  layers (see [ADR 0007](0007-export-sef-format.md)) have treated dead
  code found during review.
- Every real HTTP error path a client can actually trigger is tested
  directly against the running app via `fastapi.testclient.TestClient`
  (a dev-only dependency, `httpx`, backs it): a duplicate case ID (409),
  an invalid request body caught by Pydantic before it reaches any route
  body (422), a reference to a nonexistent evidence item or clip (400 or
  404, matching whichever `CaseError` the case-store layer itself
  raises), and a case ID that resolves to nothing in the workspace (404)
  on every resource type, not just `/cases/{case_id}` itself.
- The audit-ledger integrity endpoint is tested against both a healthy
  case and one whose ledger file was tampered with directly on disk
  between requests — the same technique earlier layers used to prove a
  broken chain is actually detected, not merely typed as a possible
  response.

## Verification run before this was committed

- `pytest`: 386/386 passing, 100% line coverage across the entire
  `pramaan` package, zero warnings with `DeprecationWarning` promoted to
  an error.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a
  freshly created Python 3.12 venv, matching CI's own
  `pip install -e ".[dev,analysis]"` install exactly.

## Consequences

With acquisition, filesystem interpretation, recovery, integrity,
timeline, case management, export, and both report documents all now
reachable over one HTTP interface, the examiner-facing UI is the
remaining layer — the one component of the originally planned stack
that turns this pipeline into something an investigator drives directly
rather than through raw HTTP requests.
