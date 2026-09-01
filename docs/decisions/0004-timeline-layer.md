# ADR 0004 — Timeline layer

**Status:** accepted
**Scope:** `pramaan/timeline/`

## What was built

- `model.py` — `Segment`, `Gap`, and `Timeline`, addressed by channel and
  wall-clock time rather than disk offset. Deliberately knows nothing
  about profiles, clips, or disk images: it takes typed `(channel, start,
  end, kind)` data from whatever produced it (an index walk, a carver run,
  a manual annotation) and answers coverage questions — what exists on a
  channel, and what time ranges have nothing covering them. `SegmentKind`
  distinguishes `RECORDED` (index-confirmed) from `RECOVERED` (carved, no
  index backing it) as an epistemic fact, not a status label — this
  mirrors the two recovery paths built in ADR 0002 directly.
- `gaps.py` — classifies what a gap or a `RECOVERED` segment actually
  means, grounded in the three-way deletion taxonomy from the Honeywell
  paper already cited in `docs/sources.md` (format-based / expiration /
  overwrite, each looking different in the evidence). Every classification
  carries its `rationale` as explicit text, not just a category label —
  an examiner or a court needs to see why, not just what.
- `clock.py` — Theil-Sen (median-of-pairwise-slopes) regression fitting a
  recorder's own clock against independently-verified true-time anchors.
  Chosen over ordinary least squares specifically for robustness to a
  single bad anchor (a misread OSD timestamp, a stale NTP record) — this
  is not a hypothetical concern for a tool whose anchor sources include
  OCR.

## Design decision: a straight interval model, not reused byte-offset code

`Timeline.gaps_for` uses the same complement-of-coverage shape as
`pramaan.recovery.extents.compute_gaps`, but is not built on top of it —
one operates on integer byte offsets, the other on `datetime`s, and
forcing a shared generic implementation across both would have cost more
in abstraction than the ~15 lines of duplicated shape are worth at this
scale. Each is independently and fully tested.

## Bug found and fixed during review

None in the implementation itself survived to the first test run — every
test passed on the first execution. Review still caught a real defect in
the **test suite**: `test_gaps_for_merges_overlapping_segments_before_
computing_gaps` originally reached for `Gap` via an inline
`__import__("pramaan.timeline.model", fromlist=["Gap"])` call instead of a
top-level import, for no reason other than the test being written in a
hurry. Fixed to a plain import — not a functional bug, but exactly the
kind of thing that would look sloppy to anyone reading the test file, so
it did not stay.

## What review confirmed was handled correctly, by design

- `Timeline.overlapping_pairs` deliberately does not resolve overlapping
  segments (merge them, prefer one) — two different accounts of the same
  time range is itself a finding worth surfacing, not something a
  coverage model should silently pick a winner for.
- `gaps.find_anomalies` treats a gap with perfectly *contiguous* sequence
  numbers on both sides as `UNEXPLAINED_GAP`, not as resolved — sequence
  continuity says the recorder's counter looks normal, which is a
  different fact from *why* a time range has no data at all, and the two
  must not be conflated. Tested directly as its own case, not assumed to
  fall out of the discontinuity test.
- Theil-Sen's robustness claim is not just asserted — `test_theil_sen_
  tolerates_one_outlier_anchor` and a companion test that runs the *same*
  corrupted anchor set through ordinary least squares (`np.polyfit`)
  confirm both halves of the claim: Pramaan's estimator stays close to
  ground truth, and the naive alternative it was chosen over would not
  have. The second test exists so a future change that quietly swapped
  the estimator would fail loudly, not silently lose the property this
  ADR is justifying.

## Verification run before this was committed

- `pytest`: 198/198 passing, 100% line coverage across
  `pramaan.timeline` (and every layer under it), zero warnings with
  `DeprecationWarning` promoted to an error.
- `ruff check` and `mypy`: clean.
- All of the above run under both a real Python 3.11 and a real Python
  3.12 interpreter before pushing — the process fixed after ADR 0003.

## Consequences

Turning a `ClipRecord`'s decoded timestamp field or a carved clip's
inferred position into an actual `Segment` — and running OSD OCR to
produce `ClockAnchor`s in the first place — is case-management and
analysis-layer work, not this layer's. `pramaan.timeline` is deliberately
a pure model over already-typed data, so it stays independently testable
without needing a disk image, a profile, or ffmpeg anywhere near its
tests.
