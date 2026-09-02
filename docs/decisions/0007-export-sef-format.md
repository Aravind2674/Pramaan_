# ADR 0007 — Export layer: the Surveillance Evidence Format

**Status:** accepted
**Scope:** `pramaan/export/`

## What was built

The SEF bundle: a documented, versioned ZIP with a manifest validated
against a published JSON Schema, the artifacts it describes, an optional
audit-ledger excerpt, and an optional Ed25519 signature over the manifest.
This is the direct answer to the "standardized" word in the problem
statement's title — the schema is published in the package specifically so
a third party can validate a bundle's structure without ever importing
Pramaan.

`build_sef_bundle` constructs one; `validate_sef_bundle` independently
checks one — every artifact's declared hash and size against its actual
content, an included ledger excerpt's internal chain consistency and its
match against the manifest's declared head hash, and a signature's
validity against its bundled public key.

## Design decision: the signature is never a field inside the manifest

A signature covering "this JSON document, including its own signature
field" is circular — every way to make that work in practice (sign a
redacted copy, sign some canonical form that excludes the field) leaves a
gap between what was actually verified and what actually ships in the
bundle, exactly the kind of subtle mismatch a careless implementation
could hide behind. The schema (`sef_manifest.schema.json`) has no
signature property at all. Signing is two separate sidecar files instead —
`manifest.json.sig` (the raw signature, hex-encoded) and
`examiner_public_key.pem` — so `manifest.json` never needs to know it
might be signed, and verification is exactly "hash these exact bytes,
check that signature," with nothing to reconstruct or redact first.

## Design decision: a trusted-key check is separate from a valid-signature check

`validate_sef_bundle` distinguishes "this signature verifies against
*some* bundled public key" from "this signature verifies against *the*
public key the caller expected." The first proves the manifest hasn't
been altered since whoever holds that key signed it. It says nothing about
who that key belongs to — binding a key to a specific named examiner is a
real-world trust decision (a registered fingerprint, a certificate chain)
that lives outside a single bundle and outside what this function can
determine from the bundle alone. Conflating the two would let a bundle
"verify" in a way that implies more assurance than the check actually
gives.

## A real refactor to an earlier, already-shipped layer

Validating an embedded ledger excerpt needs the same chain-verification
logic `Ledger.verify_chain()` already has, but an excerpt from a ZIP is a
plain list of parsed entries, not a file-backed `Ledger`. Rather than
reimplement the check against a list (risking the two definitions drifting
apart over time) or force a temp-file round trip just to get a `Ledger`
object, the verification logic was extracted from
`pramaan.integrity.ledger.Ledger.verify_chain` into a standalone
`verify_entries(entries)` function, with the method now delegating to it.
Confirmed safe with a direct test (`verify_chain() == verify_entries
(ledger.entries)` on the same data) rather than assumed from the refactor
being "obviously" behavior-preserving — and this ADR's own test suite
depends on that guarantee actually holding.

## What review caught as genuinely reachable, not padding for coverage

An empty `case_id` (or any other required string) passes Python's own
type checks — it's still a `str` — but fails the schema's `minLength`
constraint. Confirmed as a real path a caller can hit, not a
formality: added a direct test with an empty `case_id`, checking
`build_sef_bundle` fails loudly via `SefError` before writing any bytes,
rather than assuming the schema-validation call could never actually
trip given how the function's own parameters are typed.

## Verification run before this was committed

- `pytest`: 284/284 passing, 100% line coverage across `pramaan.export`
  and the `pramaan.integrity.ledger` refactor, zero warnings with
  `DeprecationWarning` promoted to an error.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a real
  Python 3.12 interpreter.

## Consequences

`pramaan.report` (the PDF report and BSA §63(4) certificate) is the next
layer, and it composes on top of both `pramaan.case` and this one — a
report generator reads a `Case`, and a completed case export is exactly a
SEF bundle with the report PDF added as one more artifact.
