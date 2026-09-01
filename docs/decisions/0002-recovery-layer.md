# ADR 0002 — Recovery layer

**Status:** accepted
**Scope:** `pramaan/recovery/`

## What was built

Three distinct ways footage comes back, matching how little the tool is
told going in:

- `index_walk.py` — a known vendor profile's own index is intact. Works
  generically for any profile with a `recurring` signature and `channel`/
  `sequence`-tagged fields, so it already works against the real Dahua
  profile without any Dahua-specific code.
- `carver.py` — the index entry is gone, but the payload survives in space
  no index claims. Scans directly for H.264 structure and reconstructs
  clip boundaries with no help from any profile. Includes the lossless
  remux (`-c:v copy`) and the bit-exactness proof (extract the bitstream
  back out of the export and compare).
- `profiler.py` — the vendor's filesystem is unknown entirely. Promotes the
  standalone proof of concept that validated this idea into production
  code: infers block cadence, header length, a magic signature, and typed
  fields (timestamp/sequence/length/channel) from raw bytes alone, and
  renders the result as a loadable, schema-valid draft profile.
- `extents.py` and `h264.py` — the shared plumbing (interval arithmetic;
  Annex-B NAL scanning) both the carver and the profiler need.

## Two real bugs found and fixed during review — not just findings, fixes

**`normalize_slice_stream` included the NAL header byte as if it were slice
payload.** The comparison this function exists for (proving a remux didn't
alter the coded picture data) still happened to pass in the first draft
because both sides of every comparison made the same mistake identically —
which is exactly the kind of bug a test that only checks self-consistency
would never catch. A test asserting an exact expected byte string (built
independently of the implementation) caught it immediately. Fixed to slice
from `header_offset + 1`.

**`walk_container_records` tracked one "current" clip regardless of
channel.** A multi-camera recorder ordinarily interleaves channels'
records on disk — channel 0, channel 1, channel 0, channel 1... A single
"most recently seen" clip variable treats every channel switch as a
discontinuity, so interleaved channels never grouped into more than one
record each, even when each channel's own sequence was perfectly
contiguous. Fixed to track one open clip per channel (`dict[int,
ClipRecord]`), closing and re-sorting only at the point where a channel's
own sequence actually breaks.

Both were caught by a test that modeled a realistic scenario (bit-exactness
via independent verification; genuinely interleaved channels) rather than
the easiest scenario to construct — which is the actual reason those tests
existed, not incidental.

## Dead code removed rather than left uncovered

Three defensive branches, each traced through to prove they were
unreachable given the actual call-site invariants, were deleted instead of
padded with a coverage-satisfying test for an impossible input:

- `carve_h264_clips`'s `if not payload: continue` — a slice anchored on a
  real SPS-type NAL (type 7) always begins with a non-zero header byte
  positioned before whatever gets trimmed from the tail; `rstrip` cannot
  empty it.
- `_infer_block_geometry`'s `if diffs.size == 0` — anchors come from
  `find_offsets`, which scans strictly left-to-right with no duplicates;
  every diff between them is positive by construction.
- `_infer_fields`'s `try/except struct.error` around `unpack_from` — the
  enclosing loop already checked `offset + width <= header_length` and
  every row is exactly `header_length` bytes; the unpack cannot fail.

Each removal has a comment recording the invariant that makes it safe,
so a future change to the calling code has something concrete to falsify
if it breaks that invariant.

## What was verified as genuinely reachable and given a real test instead

`region.length == 0` in the carver (a caller can legitimately pass a
zero-length `Extent`), `RemuxError` from `remux_to_mp4` itself and not just
`verify_bitexact` (a bad destination path), a headerless layout and a
no-dominant-header-offset layout in the profiler (both real, if unusual,
recorder designs), no-dominant-magic-byte, and the profile-has-no-length-
role fallback in `index_walk`. Every one of these got a constructed test
proving the actual behavior, not just a coverage number.

## Verification run before this was committed

- `pytest`: 98/98 passing, 100% line coverage across `pramaan.recovery`
  (and the layers under it), zero warnings with `DeprecationWarning`
  promoted to an error.
- `ruff check`: clean.
- `mypy`: clean.
- A real editable install in a second, freshly-created isolated venv,
  confirming the new subpackage is picked up with no packaging changes
  needed (`pramaan*` already matches it).

## Consequences

`index_walk.walk_container_records` is now the first place role-tagged
profile fields (`channel`, `sequence`, `length`) are consumed generically
rather than referenced by name — any future profile that tags those roles
correctly gets index-walk recovery for free.
