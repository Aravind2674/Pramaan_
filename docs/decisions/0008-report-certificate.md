# ADR 0008 — Report layer: the Section 63(4) certificate

**Status:** accepted
**Scope:** `pramaan/report/`

## What was built

`generate_certificate_pdf` — a PDF renderer for the certificate the
Bharatiya Sakshya Adhiniyam (BSA) 2023 Section 63(4) requires before an
electronic record is admissible at all. The Schedule splits it into two
parts, and this module mirrors that split exactly rather than flattening
it into one generic form: **Part A** (`CertificatePartA`), completed by
the person who had the device under their control, declaring lawful
control and proper functioning; **Part B** (`CertificatePartB`),
completed by a technical expert, carrying the free-text technical
statement the Schedule leaves to the expert's own words. Both parts
declare a device (`DeviceDetails`, with **DVR** as a named category
alongside Computer/NVR/Mobile Phone/Flash Drive/Hard Disk/Other — not an
approximation forced into "Computer") and a hash (`HashDeclaration`,
SHA1/SHA256/MD5/Other, matching the Schedule's own checkboxes).

No commercial or open-source DVR forensic tool surveyed during this
project's research generates this certificate; every one stops at a
vendor-neutral export report. This is a direct, cited, unmet requirement
of the problem statement, not a bolted-on nicety.

## Design decision: Pramaan attests to nothing itself

Every dataclass here raises `CertificateError` in `__post_init__` if the
underlying attestation is missing — `CertificatePartA` refuses to
construct unless both `lawful_control_declared` and
`functioning_properly_declared` are `True`; `CertificatePartB` refuses to
construct with a blank `technical_statement`. The point isn't
input-validation hygiene — it's that this module has no code path that
lets a caller produce a signed-looking certificate without a real human
custodian and a real human expert having actually supplied their own
declaration and their own words. The PDF is a faithful rendering of an
attestation someone else made, never a attestation Pramaan manufactures
on their behalf.

## Design decision: the Schedule wording is flagged, not silently trusted

The exact field structure was confirmed from a secondary bare-act
reproduction — the primary source (indiacode.nic.in) blocked automated
fetch during this project's research (see `docs/sources.md`). Rather than
present the certificate as unquestionably authoritative, every generated
PDF carries a disclaimer paragraph naming this directly and pointing at
the primary source to verify before an actual filing. A legal-document
generator that hides its own provenance gap is worse than one that states
it plainly.

## Bug caught before commit: em dashes silently corrupt in extracted text

Manual verification generated a PDF and used `pypdf` (dev/test-only — see
`pyproject.toml`) to extract its text back out, rather than trusting that
`reportlab.platypus` producing a nonzero-size file meant the content was
correct. That surfaced a real defect: the two literal em dash (`—`)
characters used in `Paragraph(...)` text for "Part A — Certificate..." /
"Part B — Certificate..." and the device-table fallback values round-
tripped through pypdf extraction as `U+FFFD` replacement characters, not
as em dashes. On a legal document, a corrupted glyph is a real defect,
not a cosmetic one. Fixed by replacing both actually-rendered instances
with ASCII (`"Part A - Certificate..."`, `"N/A"` for missing optional
device fields) — docstring/comment em dashes elsewhere in the file were
left alone since those never flow into rendered output. A permanent
regression test (`test_pdf_text_has_no_unicode_replacement_characters`)
extracts text from a full generated certificate and asserts no `U+FFFD`
character appears anywhere in it.

## Two real mypy findings caught during 3.11/3.12 verification

`DeviceDetails.display_type` and `HashDeclaration.display_algorithm`
return `self.other_device_type` / `self.other_algorithm_name` — typed
`str | None` — whenever the field is `"Other"`. `__post_init__` already
guarantees that value is non-`None` in that branch, but mypy has no way
to see across that boundary. Fixed with an explicit `assert ... is not
None` in each property, documenting the invariant a reader (or mypy)
would otherwise have to trust blindly, rather than silencing the error
with a cast that asserts nothing.

Separately, `reportlab` ships no type stubs or `py.typed` marker;
`types-reportlab` was added to the `dev` extras (mirroring the existing
`types-jsonschema` / `types-PyYAML` pattern) rather than suppressing the
import with a blanket `ignore_missing_imports` override, since real,
versioned stubs exist and are worth having.

## What review caught as genuinely reachable, not padding for coverage

- Every `CertificateError` branch (unknown `device_type`, `"Other"`
  without its name, unknown hash `algorithm`, `"Other"` without its name,
  blank hash `value`, Part A missing either declaration, Part B with a
  blank `technical_statement`, `generate_certificate_pdf` called against
  an already-existing `dest_path`) is exercised directly — these are all
  real caller mistakes a validation layer is specifically there to catch,
  not defensive code with no real caller.
- Content tests extract PDF text with `pypdf` rather than only checking
  file existence and size, and specifically assert the DVR device
  category, the hash value, the selected hash-algorithm checkbox (and
  that *other* algorithms are *not* marked), the technical statement, and
  the primary-source disclaimer all actually appear in the rendered
  output.

## Verification run before this was committed

- `pytest`: 309/309 passing, 100% line coverage across the entire
  `pramaan` package (not just `pramaan.report`), zero warnings with
  `DeprecationWarning` promoted to an error.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a
  freshly created Python 3.12 venv, matching CI's own
  `pip install -e ".[dev,analysis]"` install exactly.

## Consequences

`pramaan.report.case_report` (planned) is the next module — the full
narrative case report that composes a case summary, methodology,
findings, and exhibit list from a `pramaan.case.store.Case`, with this
certificate as one of its accompanying artifacts rather than a
standalone document. After that, the API layer (`pramaan.api`) is what
turns the whole pipeline into something a UI can actually drive.
