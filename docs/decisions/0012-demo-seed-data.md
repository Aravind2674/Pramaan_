# ADR 0012 — Demonstration data: a seed script, not an API feature

**Status:** accepted
**Scope:** `pramaan/demo/`, `scripts/seed_demo_case.py`

## What was built

`pramaan.demo.seed_demo_case` populates a `CaseWorkspace` with one
synthetic case: a fictional warehouse break-in recorded across a Dahua
DVR (two channels) and a Hikvision NVR (two more), with a deliberate mix
of intact, corrupted, and carved footage designed to exercise every
anomaly category `pramaan.timeline.gaps` recognizes -- a recovered
segment filling part of a gap, a sequence discontinuity with no
recovered footage at all, and a corrupted (not missing) stretch. Three
examiner findings reference the specific clips involved. `scripts/
seed_demo_case.py` is the thin CLI wrapper an examiner or a demo runs
directly: `python scripts/seed_demo_case.py --workspace <dir>`.

This exists because an empty workspace does not show what the tool
actually does -- a case list with nothing in it, a timeline with no
segments, a certificate form with nothing to reference. The seed script
gives the API and UI a populated, realistic case to demonstrate against
without touching real evidence.

## Design decision: a seed script, never an API endpoint

The obvious alternative -- a `POST /demo/seed` route wired into
`pramaan.api` -- was rejected outright. A tool whose entire premise is
producing evidence trustworthy enough for a court should not ship an
HTTP endpoint whose job is generating fictional evidence indistinguishable
in shape from real evidence. Keeping this a standalone script that an
operator runs deliberately, before ever pointing the API at a workspace
meant for a real case, draws that line structurally rather than by
convention or documentation alone. `pramaan/demo/` is also excluded from
what any production code path imports -- `pramaan.core`, `.recovery`,
`.case`, `.export`, `.report`, and `.api` have no dependency on it in
either direction.

## Design decision: every hash is real, over a payload the module owns

`_synthetic_sha256` computes an actual `hashlib.sha256` over a
deterministic string this module builds itself
(`f"pramaan-demo-synthetic-payload::{label}"`), rather than hard-coding
a plausible-looking hex string. Two consequences of that: the same
`label` always reproduces the same hash (verified directly -- seeding
the same evidence description into two different workspaces yields
byte-identical evidence hashes), and nothing in this module ever writes
a value into the `sha256` column that doesn't correspond to bytes that
actually hash to it. A demo is still real code; it doesn't get a pass on
fabricating the one field this entire project exists to make trustworthy.

## Design decision: relative to the incident's own clock, not `datetime.now()`

Every timestamp is built from a fixed `_INCIDENT_START`
(`2026-08-30T01:00:00Z`) plus a minute offset, not the wall-clock time
the script happens to run at. A demo seeded today and a demo seeded next
year produce byte-identical case data -- useful for the deterministic
hash property above, and for anyone diffing two seed runs to confirm
nothing drifted.

## What review caught as genuinely reachable, not padding for coverage

- Seeding into a workspace that already has a case at the requested ID
  raises `WorkspaceError`, exactly like every other case-creation path
  in this project (`Case.create`, `CaseWorkspace.create_case`) --
  tested directly, and the CLI surfaces it with a `--force` hint rather
  than a bare traceback.
- The CLI's `--force` flag is tested as an actual subprocess round trip
  (seed, fail on a second seed, succeed with `--force`, confirm the
  case file exists under a custom `--case-id`) via
  `tests/integration/test_seed_demo_case_script.py`, alongside the
  `pramaan.demo.seed` unit tests that check the resulting case's
  contents (evidence item count, clip count and kinds, finding count, a
  valid ledger chain, and that `find_anomalies` actually flags the
  recovered-from-unallocated and sequence-discontinuity segments this
  module was specifically built to produce).

## Verification run before this was committed

- `pytest`: 402/402 passing, 100% line coverage across the entire
  `pramaan` package (the CLI script itself is exercised via the
  subprocess integration test rather than coverage-instrumented, the
  same treatment the project's other CLI-shaped entry points would get).
- `ruff check` and `mypy`, now covering `scripts/` as well as `pramaan/`:
  clean under both a real Python 3.11 and a freshly created Python 3.12
  venv.
- CI additionally smoke-tests the script itself (seed, then `--force`
  re-seed) as its own step, independent of the pytest run.

## Consequences

None to the production pipeline -- this is tooling around it, not a new
layer. The one thing worth watching: if `pramaan.case.store`'s schema
or `pramaan.timeline.gaps`'s anomaly rules change in the future, this
module's synthetic scenario is exactly the kind of consumer that would
need a matching update, the same as any other caller of those APIs.
