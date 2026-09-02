# ADR 0009 — Report layer: the narrative case report

**Status:** accepted
**Scope:** `pramaan/report/case_report.py`, `pramaan/report/_styles.py`

## What was built

`generate_case_report_pdf` — the document that accompanies the
Section 63(4) certificate ([ADR 0008](0008-report-certificate.md)) and
the SEF export bundle ([ADR 0007](0007-export-sef-format.md)): a full
narrative report composed directly from a live
`pramaan.case.store.Case`. It reads, never infers: case summary,
evidence items (with device details, hashes, and write-block-attestation
status), a per-channel recovery coverage summary, the full clip exhibit
list, every recorded examiner finding, an optional timeline anomaly
analysis, and the audit ledger's own chain-verification result. Every
number, hash, and status in the document is computed from the case
store's own tables at generation time — this module adds no judgement
of its own about what the evidence means.

## Design decision: gap analysis needs a caller-supplied window, and says so when it's missing

`pramaan.timeline.gaps.find_anomalies` requires an *expected recording
window* to classify what's missing — there is no way to derive a
recorder's actual retention period from the case store alone (a case
might have three clips spanning ten minutes or three months; nothing in
the schema says which is the deployment's *whole* expected window).
Rather than guess one from the earliest and latest recorded timestamps
(which would silently misclassify a partially-processed case as fully
gapless, or manufacture a false "gap" at its edges), the report accepts
an optional `GapAnalysisWindow` and states plainly when it was omitted
— "Skipped -- no expected recording window was supplied" — rather than
either running a fabricated analysis or omitting the section without
explanation. An examiner reading the PDF should never have to wonder
whether gap analysis was silently forgotten.

## A real layout bug caught by extraction-based testing, not by looking at the PDF

The first evidence-item table put SHA-256 (64 hex characters) in one
column among five others. Two things went wrong at once, both only
visible once `pypdf` was used to extract text back out (not from staring
at the rendered page): the six column widths summed to more than the
usable page width, so the table was quietly laid out at less than the
requested widths -- and squeezed into a genuinely narrow cell, a 64-
character run with no natural break point gets force-wrapped mid-string
by reportlab, with no hyphen or other marker. Extracted back out, that
looks like two disconnected fragments, not one hash -- exactly the kind
of corruption `certificate.py` already learned to watch for with em
dashes ([ADR 0008](0008-report-certificate.md)), from an entirely
different cause.

The fix was structural, not cosmetic: evidence items and clip exhibits
are no longer table rows at all. Each is its own block -- a bold header
line, a line of short key/value fields, and (the fix that actually
matters) the hash on its **own full-width monospace line**, the same
pattern `certificate.py` already uses successfully for its hash field.
At 9pt Courier, a 64-character hash needs about 122mm, comfortably under
a full A4 content width (~174mm) but nowhere close to fitting in a
40mm table cell -- the numbers were never checked against each other
until this bug forced it. A permanent regression test extracts text from
a report containing a full-length hash and asserts the exact 64-character
string appears intact and contiguous.

## Design decision: styles are shared, not duplicated a second time

`certificate.py` already defined five `ParagraphStyle`s (title, subtitle,
heading, body, mono, small) that this module needed verbatim. Rather
than paste a second copy — guaranteed to drift the first time only one
of the two got a visual tweak — `_build_styles` was extracted into
`pramaan/report/_styles.py` as `build_report_styles()`, and
`certificate.py` was updated to import it. Confirmed non-breaking by
re-running `certificate.py`'s full existing test suite (unchanged)
before extending it with `case_report.py`'s own tests.

## What review caught as genuinely reachable, not padding for coverage

- An evidence item's write-block attestation has three real display
  states, not two: absent (`"Not checked"`), refused
  (`"Write-open refused"`), and *permitted* (`"Write-open permitted"`,
  from `pramaan.core.writeblock` — an ordinary writable working copy,
  not a failure). All three are exercised directly.
- A clip's optional free-text `note` field (set, for example, when a
  carved clip's frame count is a known lower bound) is real, examiner-
  authored content, not internal bookkeeping — a real case can have a
  clip with one, and the report renders it.
- An empty case (freshly created, nothing added yet) must still produce
  a complete, valid document that states each section's emptiness
  honestly ("No evidence items have been recorded in this case.") rather
  than crash or silently print nothing — this is tested directly, since
  a report generated moments after `Case.create()` is a genuinely
  reachable real-world case, not an edge case invented for coverage.
- A ledger with a tampered entry produces a `ChainVerification` with
  `valid=False`; the report's own text (`"BROKEN"`, the break index, and
  the stated reason) reflects that directly, tested against a
  deliberately corrupted ledger file rather than only a healthy one.

## Verification run before this was committed

- `pytest`: 332/332 passing, 100% line coverage across the entire
  `pramaan` package, zero warnings with `DeprecationWarning` promoted
  to an error.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a
  freshly created Python 3.12 venv, matching CI's own
  `pip install -e ".[dev,analysis]"` install exactly. (`ruff`'s `DTZ`
  rules required `datetime.now(UTC)` in production code and
  `tzinfo=UTC` throughout the new tests -- both fixed to match the
  timezone-aware convention `pramaan.case.store` and the timeline test
  suite already use.)

## Consequences

With both report documents in place, `pramaan.api` (a FastAPI backend
exposing acquisition, recovery, the case store, export, and both report
documents as one coherent service) is the next layer — the one that
turns this pipeline into something a UI can actually drive.
