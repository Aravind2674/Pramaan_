# ADR 0006 — Case store

**Status:** accepted
**Scope:** `pramaan/case/`

## What was built

`pramaan.case.store.Case` — the aggregation point every earlier layer
deliberately left to a caller. It is the first place in this project that
composes across layers rather than staying a standalone primitive:

- One portable SQLite file per investigation (plain `sqlite3`, not an ORM
  — a case file has to be openable by a court's own tooling, or by
  `sqlite3` from a bare command line, without this project's dependency
  stack installed anywhere).
- Evidence items, recovered clips, and examiner findings, each with a
  typed dataclass and CRUD methods.
- `record_index_walk_clip` / `record_carved_clip` convert
  `pramaan.recovery`'s own result types directly, rather than asking a
  caller to hand-map fields.
- `build_timeline()` constructs an actual
  `pramaan.timeline.model.Timeline` from whatever clips in the case have a
  known time range — the first place two previously-independent layers
  are joined into one object.
- **Every mutating method appends one entry to this case's
  `pramaan.integrity.ledger.Ledger` before returning** — not opt-in
  instrumentation a caller has to remember to add, but part of what
  "adding an evidence item" means in this tool.

## Design decision: the plain constructor cannot create a case

Caught in review, before any test was written against it: the first draft
let `Case(path)` silently create an empty, schema-only SQLite file at
`path` if nothing existed there yet — an accidental side effect of
`sqlite3.connect()`'s own behavior, not a deliberate choice. A typo'd path
would produce a stray, uninitialized case file instead of a clear error,
and that file would sit there looking like a real (if empty) case to
anyone who found it later. Fixed before it ever reached a test: the plain
constructor now requires the file to already exist, and `Case.create()` is
the only way to make a new one. `info()` still fails clearly and
separately (`CaseError`, not a row of `None`s) if it's ever pointed at a
file that has the schema but was never actually initialized through
`create()` — checked directly by constructing exactly that malformed case
by hand in a test, not assumed to be covered by the constructor's own
check.

## Design decision: carved clips must be given a channel explicitly

`record_carved_clip` takes `channel` as a required, separate parameter,
not something inferred from the `CarvedClip` itself — because carving
(recovering footage from unallocated space with no filesystem index
pointing at it) has no way to know which camera a recovered clip came
from. Silently defaulting or guessing a channel here would let a
recovered clip's channel attribution look more certain in a case file than
it actually is. The caller — an examiner's own judgement, or a later
cross-referencing step — supplies it, or doesn't call this method until
they can.

## A real API asymmetry caught during review, not by a failing test

`get_evidence_item` was public and tested for the missing-record case from
the start; the equivalent lookup for a finding was a private
`_get_finding`, called only right after an insert, with no way for a
caller to look one up later. Coverage flagged the "not found" branch as
unreachable — correctly, since the only call site could never trigger it —
but the right fix was not to delete the dead branch (as was done for
several genuinely-unreachable checks in earlier layers). Here the branch
being unreachable was itself the symptom: the method should have been
public and useful all along, matching `get_evidence_item`'s own shape.
Promoted to `get_finding`, and the "missing" case is now exercised through
the public API a caller would actually use.

## Verification run before this was committed

- `pytest`: 252/252 passing, 100% line coverage across `pramaan.case`
  (and every layer under it), zero warnings with `DeprecationWarning`
  promoted to an error. Includes a direct test that every mutating method
  (`create`, `add_evidence_item`, `add_clip`, `set_clip_time_range`,
  `add_finding`) produces exactly the ledger entries it should, in order —
  not just that the ledger exists.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a real
  Python 3.12 interpreter. One new mypy finding on this layer specifically
  — `sqlite3.Cursor.lastrowid` is typed `int | None` by its stub,
  correctly, since it can genuinely be `None` after a non-INSERT
  statement; here it never is, since every call site is checked
  immediately after an INSERT this method just issued. Resolved with an
  explicit, commented `assert`, which is a real runtime safety check as
  well as a type narrowing, not a mypy-only annotation.

## Consequences

`pramaan.export` (SEF bundles) and `pramaan.report` (the PDF report and
BSA §63(4) certificate) both read from a `Case` rather than from
individual layer objects directly — this is the object a report generator
should ask "what evidence, what clips, what findings, what does the ledger
say happened," not something built by re-deriving that from scratch.
