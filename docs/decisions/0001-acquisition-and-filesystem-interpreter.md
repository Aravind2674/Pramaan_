# ADR 0001 — Acquisition layer and vendor-profile interpreter

**Status:** accepted
**Scope:** `pramaan/core/`, `pramaan/fs/`

## What was built

- `pramaan.core`: `DiskImage`, a read-only view over an acquired source with
  no write path at all (structural, not policy); `hash_image`/`StreamingHash`
  for single-pass multi-algorithm hashing; `verify_source_read_only`, an
  honest write-block *attestation* (see below for why not "verification").
- `pramaan.fs`: a declarative vendor-profile format (`profile.schema.json`),
  an interpreter that compiles a profile into a working struct reader
  (`FilesystemInterpreter`), and a fingerprinting registry that ranks
  candidate vendors by signature match count rather than picking one.
- Two shipped profiles: `dahua_dhav.yaml` (every field offset read directly
  from FFmpeg's `libavformat/dhav.c`, confidence: `verified`) and
  `hikvision_master_sector.yaml` (only the signature is at a confirmed
  offset; every other Master Sector field is documented by name and order
  only, confidence: `partial`) — see `docs/sources.md`.

## Review — four lenses, applied adversarially before this was called done

**Security (the input is a seized, attacker-controlled disk image by
definition).** Profile YAML is loaded with `yaml.safe_load`, never `yaml.load`
— no arbitrary object deserialization from a profile file. Every declared
field's `ascii` decode uses `errors="replace"` rather than raising on
malformed bytes, since a corrupted or deliberately booby-trapped image must
produce a clear decode error, never an unhandled crash mid-case. Every read
is bounds-checked once, centrally, in `DiskImage.read` — no profile-parsing
code re-implements its own bounds arithmetic and no path can read outside
the image. No `eval`/`exec`/`pickle` anywhere in either package.

*Open item, not blocking:* `find_signatures` for a short recurring signature
(Dahua's magic is 4 bytes) will spend time re-verifying incidental false
matches in random/high-entropy regions of a large image, since a 4-byte
pattern recurs by chance roughly every 4 billion bytes but "no worse than
that" isn't provably true against adversarial content. Not a correctness or
memory-safety issue — `matches_at` always re-verifies before accepting a
candidate — but worth revisiting for throughput once real multi-gigabyte
images are available to benchmark against.

**Correctness.** The Dahua bitfield date decode is tested against a
hand-computed example (2024-03-14 21:48:49) built independently of the
production code, not against a value the same code produced — the point of
that test is to catch a mistake in the formula itself, which a round-trip
test cannot do. Boundary conditions (empty image, zero-length read, a field
that would read past the end of the image, a signature whose type-byte
check would read past the end) are each an explicit test, not incidentally
covered. 100% line coverage on both packages, achieved by adding tests for
the gaps coverage reported — not by writing tests to hit numbers.

**Forensic soundness.** `DiskImage` has no `write` method; that is what
enforces "evidence is never modified," not a docstring. `verify_source_read_only`
is named and documented as an *attestation*: it reports what the OS did
when asked to open the source for writing, and says explicitly that this
proves something for a raw device behind a real write-blocker and proves
much less for an ordinary file. Claiming more than that — "verified
write-blocked" — would be a real defect in a courtroom-facing tool, not a
rounding error. The Hikvision profile declining to fabricate unconfirmed
offsets is the same principle: a wrong offset silently returns a wrong
timestamp or channel number, which is worse than an admitted gap.

**Fit against the plan.** Both packages correspond to L1 (Acquisition) and
L2 (Filesystem) in the architecture, and the Dahua profile is the first
vendor artifact built from a primary source rather than a synthetic proof of
concept — see `docs/sources.md` for the citation trail.

## Verification run before this was committed

- `pytest`: 47/47 passing, 100% line coverage on `pramaan.core` and
  `pramaan.fs`, zero warnings with `DeprecationWarning` promoted to an error.
- `ruff check`: clean.
- `mypy`: clean.

## Consequences

Adding a third vendor now means writing a YAML file against
`profile.schema.json`, not touching `pramaan/fs/profile.py`. Completing the
Hikvision profile is scoped as calibration work against a real disk image,
not a code change.
