# ADR 0005 — Analysis layer: OSD timestamp reading

**Status:** accepted
**Scope:** `pramaan/analysis/`

## What was built, and what was deliberately not

`pramaan.analysis.osd_ocr` reads a recorder's burnt-in on-screen timestamp
overlay via classical template matching, not a general OCR model.

This was a real scoping decision, not a default: a DVR/NVR's OSD overlay
uses a small, fixed character set (digits and a few delimiters) in one
fixed bitmap font, at one fixed screen position and scale, drawn the same
way in every frame from the same recorder — nothing like the
variable-font, variable-position natural-scene text a learned OCR model
(EasyOCR, PaddleOCR, Tesseract) is built for. Reaching for a heavy model
here would have meant either downloading pretrained weights at test time
(a network dependency and a CI slowdown this project has otherwise
avoided everywhere) or shipping opaque weights nobody here can audit the
training data of. A template-matching approach needs neither: it is fully
testable offline, and the whole method is inspectable end to end.

**There is no bundled "default" template set**, and this was a considered
reversal partway through building it: development started by generating a
generic template set from OpenCV's own font rendering, on the theory that
a rough starting point beats nothing. Empirical testing (see below)
showed the opposite — a template set rendered at a *different* effective
scale than the query, even by a couple of pixels, produces confident-looking
wrong reads, not honestly low-confidence ones. Shipping a generic set
would have meant every real user's first experience was a plausible-looking
misread. Templates must be calibrated from a labeled crop of the actual
footage being examined — the same discipline the Hikvision profile in
`pramaan/fs/profiles/` already applies (an honestly incomplete profile
over a confidently wrong one).

## Two real, non-obvious bugs found and fixed during development

**A generic template set rendered in isolation does not match a character
segmented out of a continuous string.** The first implementation rendered
each template character on its own canvas, then compared it against
characters cropped from a whole-string render. Digits matched reasonably;
delimiters (`-`, `:`) did not, because isolated rendering and inline
rendering position the same glyph a pixel or two differently within its
own crop — and a delimiter's sparse ink means that small an offset
dominates a fixed-position comparison, while a digit's dense ink mostly
tolerates it. Fixed by deriving templates from a *segmented reference
strip* — the same rendering and segmentation pipeline recognition itself
uses — rather than isolated per-character canvases.

**Adaptive per-string crop-then-rescale silently drifted the effective
font scale between different strings.** The synthetic-render helper used
during development cropped each rendered string tightly to its own ink
bounding box, then rescaled that crop to a fixed height — meaning two
different strings, with different ink extents, ended up rendered at
subtly different *effective* scales even though the same font size was
requested for both. This is exactly the failure mode the module's
templates-must-match-scale design is built to guard against, and it was
present in the *test harness*, not the module itself — meaning early
results looked like a matching-algorithm bug when the actual defect was
in how the test data was generated. Fixed by rendering at one fixed scale
and baseline for every string, which is what a real camera overlay
actually does, and is the only way the harness could exercise the design
's real precondition rather than accidentally violating it.

## A third bug, found by trying to compensate for the wrong problem first

Once a genuine sub-pixel rendering offset was suspected, `matchTemplate`
was given a small sliding-window search (±2px) to tolerate it. That
*worsened* digit accuracy, because letting every comparison search a
small alignment window let some digit templates find better accidental
partial-shape overlaps at a shifted position than at the correct one —
trading a delimiter problem for a digit problem. This was a case of
reaching for a plausible-sounding fix (tolerate misalignment) instead of
finding its actual cause (inconsistent scale in the test harness, above).
The sliding-window search was removed once the real fix landed; a ±2px
tolerance remains in the shipped module, but on top of scale-consistent
data it no longer needs to compensate for anything and doesn't reintroduce
the confusion.

## Design decision: calibrated space position, not gap-width inference

A first version tried to reinsert a literal space into recognized text by
detecting unusually wide gaps between segments. This is fragile in a way
that is easy to miss with one test case and load-bearing in practice: a
hyphen's own glyph commonly leaves more visual clearance on one side than
a digit does, so the gap immediately before a hyphen can be *wider* than a
normal inter-digit gap without there being any space there at all — and a
width-based heuristic cannot tell the two apart without already knowing
which is which. Fixed by calibrating the space's position directly from
the labeled reference transcription at calibration time (a recorder's OSD
format never changes which field the space sits between), and reinserting
it at that fixed position on every read — no per-read guessing. This also
matches how `pramaan.fs` profiles work: a fact about one recorder's layout
is established once, from a reference, not re-derived from ambiguous
evidence every time it's needed.

## Noise robustness, and why the filter is scaled off the font, not the string

A synthetic-noise test (Gaussian blur + pixel noise on a rendered strip)
produced one spurious low-confidence character in what should have been a
blank gap — exactly the intended failure mode (a caller sees a `"?"` or a
visibly low score, not a silent wrong read). The first fix — dropping any
segment narrower than some fraction of the *current query string's own
median* character width — broke colon recognition, because a colon is
genuinely narrower than a digit in the reference font, and a
median-of-this-string threshold cannot distinguish "narrow because it's
noise" from "narrow because it's a real narrow character." Fixed by
referencing the *template set's own* narrowest calibrated character
instead: a stable, font-specific fact about how narrow a real character in
this recorder's font can be, established once at calibration time.

## Verification run before this was committed

- `pytest`: 224/224 passing, 100% line coverage across
  `pramaan.analysis` (and every layer under it), zero warnings with
  `DeprecationWarning` promoted to an error. Round-trip tests cover four
  distinct real-world OSD date/time formats (`YYYY-MM-DD HH:MM:SS`,
  `MM/DD/YYYY HH:MM:SS`, `MM.DD.YYYY-HH:MM:SS`, and a fourth instance of
  the first shape), each calibrated from a reference guaranteed to cover
  every digit 0-9, reading back at exactly 1.00 confidence.
- `ruff check` and `mypy`: clean under both a real Python 3.11 and a real
  Python 3.12 interpreter, the latter with the `analysis` extra actually
  installed — the CI workflow now installs `.[dev,analysis]` specifically
  so these tests exercise real OpenCV in CI rather than skipping silently
  on a runner that never had it.
- A second Python-3.12-specific mypy finding, structurally identical to
  the one from ADR 0004 (a newer numpy's stricter return-type stub for
  `.any(axis=...)`), fixed the same way: an explicit, commented `cast()`
  recording that the narrowing is verified, not assumed.

## Consequences

Turning an `OcrResult` into an actual
`pramaan.timeline.clock.ClockAnchor` needs an independently-verified
true-time source paired with it — this module produces only the
recorder's own claimed reading, not a verified fact, and composing the
two is case-management work, not this layer's.
