"""
On-screen-display timestamp reading via template matching, not a general
OCR model.

A DVR/NVR's burnt-in timestamp overlay uses a small, fixed character set
(digits and a handful of delimiters) rendered in one fixed bitmap font, at
one fixed screen position and scale, by one recorder — nothing like the
variable-font, variable-position natural-scene text a general OCR model is
built for. Matching known glyph templates against a candidate region is
more reliable for this narrow, constrained task than reaching for a heavy
learned OCR pipeline, and it is fully testable offline: no model download,
no network dependency, no pretrained weights whose training data cannot be
audited.

**Templates must be calibrated at the same scale as the footage being
read.** A real recorder always draws its OSD at one fixed size — this
module does not adaptively rescale a query region to match a template, on
the same reasoning that :mod:`pramaan.fs` never guesses an unconfirmed
byte offset: guessing a scale correction would let a wrong-scale template
set produce a confident-looking wrong answer instead of an honestly low
one. :func:`build_templates_from_reference` calibrates a template set
directly against a labeled reference crop from the actual footage; there
is no bundled "default" font here to fall back to, because no such default
would be exact for the vendor at hand and false precision is exactly what
this module is designed to avoid.

Every result is investigative triage: the recorder's own OSD is what the
*recorder* claims the time was, not independently verified truth — pairing
an :class:`OcrResult` with an actual
:class:`pramaan.timeline.clock.ClockAnchor` still needs a true-time source
from somewhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

import numpy as np

#: Search window (pixels) matchTemplate is allowed to slide a candidate
#: within, to tolerate the few-pixel rendering-position differences that
#: are normal between two crops of the same recorder's overlay -- see the
#: module docstring on why a *scale* difference is not tolerated the same
#: way.
_ALIGNMENT_SEARCH_PX = 2

#: A segment narrower than this fraction of the narrowest *calibrated*
#: character's own width is treated as noise (a compression artifact, a
#: stray pixel cluster), not a character, and dropped before recognition
#: is attempted. Deliberately referenced against the template set, not the
#: current query string's own median width: a colon or period is a
#: genuinely narrow real character, and a threshold based on "how narrow
#: is typical in THIS string" would vary string to string and could reject
#: a real narrow character just as easily as it rejects noise. The
#: template set's own narrowest calibrated glyph is a stable, meaningful
#: answer to "how narrow can a real character in this font actually be."
_MIN_SEGMENT_WIDTH_FACTOR = 0.5

_CANONICAL_SIZE = (16, 32)  # (width, height) every glyph is normalized to before comparison


class OsdOcrError(Exception):
    """Raised for a template-calibration error (not a recognition failure
    — recognition never raises; see :class:`OcrResult`)."""


@dataclass(frozen=True)
class TemplateSet:
    """A calibrated glyph-image-per-character template set for one
    recorder's OSD font, at one fixed scale.

    ``min_reference_width`` is the narrowest calibrated character's width
    *before* canonicalization — e.g. a colon or period, which are
    genuinely narrower than a digit in almost every font. It exists so
    noise-filtering has a real, font-specific answer to "how narrow can an
    actual character be," rather than guessing from one query string's own
    composition.

    ``space_positions`` records where this recorder's OSD format places a
    literal space, calibrated from the reference transcription — see
    :func:`_space_positions`.
    """

    glyphs: dict[str, np.ndarray]
    min_reference_width: int
    space_positions: tuple[int, ...]


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    """Mean per-character confidence, 0.0-1.0. Not meaningful when
    ``text`` is empty."""
    per_char_confidence: tuple[float, ...]


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise OsdOcrError(
            "pramaan.analysis.osd_ocr requires the 'analysis' extra "
            '(pip install "pramaan[analysis]") for OpenCV'
        ) from exc
    return cv2


def _threshold(cv2_module, img: np.ndarray) -> np.ndarray:
    _, binary = cv2_module.threshold(img, 127, 255, cv2_module.THRESH_BINARY)
    return binary


def segment_characters(strip: np.ndarray, *, min_gap: int = 1) -> list[tuple[int, int]]:
    """Column ranges ``(x0, x1)`` for each ink-containing run in ``strip``
    — one range per non-space character, in left-to-right order.

    A literal space in the source text produces no ink and so is never
    returned as a range of its own; :func:`read_timestamp_overlay`
    reinserts spaces afterward at the position calibration recorded for
    them (see :func:`_space_positions`), not by inferring one from gap
    widths here.
    """
    # strip is always 2D here, so .any(axis=0) always returns an array, never
    # a scalar -- but newer numpy stubs type the overload as a union of the
    # two, since the shape isn't known statically. cast() records that this
    # is a deliberate, verified narrowing, not an unexamined type: ignore.
    col_has_ink = cast(np.ndarray, strip.any(axis=0))
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    gap_run = 0
    for x, has_ink in enumerate(col_has_ink):
        if has_ink:
            if start is None:
                start = x
            gap_run = 0
        else:
            if start is not None:
                gap_run += 1
                if gap_run >= min_gap:
                    ranges.append((start, x - gap_run + 1))
                    start = None
                    gap_run = 0
    if start is not None:
        ranges.append((start, strip.shape[1]))
    return ranges


def _drop_noise_segments(
    ranges: list[tuple[int, int]], min_reference_width: int
) -> list[tuple[int, int]]:
    threshold = max(1, round(min_reference_width * _MIN_SEGMENT_WIDTH_FACTOR))
    return [r for r in ranges if (r[1] - r[0]) >= threshold]


def _space_positions(reference_text: str) -> tuple[int, ...]:
    """Where literal spaces occur in ``reference_text``, expressed as an
    index among its *non-space* characters — position ``p`` means "a space
    follows the (p+1)-th non-space character."

    Computed once at calibration time from a labeled transcription, not
    re-guessed from pixel gap widths on every read: a query from the same
    recorder always has the same format, so where the space belongs is a
    property of *that recorder's OSD layout*, calibrated exactly like
    scale and font are — not something to infer freshly, and riskily, from
    gap widths that punctuation characters can distort (a hyphen's own
    glyph commonly leaves more visual clearance before it than a digit
    does, which a width-based heuristic cannot distinguish from a real
    space without knowing that in advance).
    """
    positions = []
    non_space_count = 0
    for ch in reference_text:
        if ch == " ":
            positions.append(non_space_count)
        else:
            non_space_count += 1
    return tuple(positions)


def build_templates_from_reference(reference_strip: np.ndarray, reference_text: str) -> TemplateSet:
    """Calibrate a :class:`TemplateSet` from one labeled crop.

    ``reference_strip`` must be a crop of the recorder's actual OSD
    overlay — same screen region, same scale, same font — and
    ``reference_text`` is what it reads, with spaces exactly where they
    visually appear. Every character used in the timestamp format this
    recorder produces (digits and whichever delimiters it uses) must
    appear in ``reference_text`` at least once; a character never seen in
    calibration is simply not something :func:`read_timestamp_overlay` can
    recognise later, and it reports ``"?"`` for it rather than guessing.
    """
    cv2 = _import_cv2()
    binary = _threshold(cv2, reference_strip)
    ranges = segment_characters(binary)
    non_space_chars = [c for c in reference_text if c != " "]
    if len(ranges) != len(non_space_chars):
        raise OsdOcrError(
            f"segmented {len(ranges)} character(s) from the reference strip "
            f"but reference_text has {len(non_space_chars)} non-space "
            "character(s) -- they must correspond one to one; check that "
            "reference_text exactly transcribes reference_strip"
        )
    glyphs = {
        ch: cv2.resize(binary[:, x0:x1], _CANONICAL_SIZE, interpolation=cv2.INTER_AREA)
        for ch, (x0, x1) in zip(non_space_chars, ranges, strict=True)
    }
    min_reference_width = min(x1 - x0 for x0, x1 in ranges)
    return TemplateSet(
        glyphs=glyphs,
        min_reference_width=min_reference_width,
        space_positions=_space_positions(reference_text),
    )


def _recognize_one(cv2_module, glyph: np.ndarray, templates: TemplateSet) -> tuple[str, float]:
    query = cv2_module.resize(glyph, _CANONICAL_SIZE, interpolation=cv2_module.INTER_AREA)
    padded = cv2_module.copyMakeBorder(
        query, _ALIGNMENT_SEARCH_PX, _ALIGNMENT_SEARCH_PX,
        _ALIGNMENT_SEARCH_PX, _ALIGNMENT_SEARCH_PX,
        cv2_module.BORDER_CONSTANT, value=0,
    ).astype(np.float32)

    best_char, best_score = "?", -2.0
    for ch, template in templates.glyphs.items():
        result = cv2_module.matchTemplate(
            padded, template.astype(np.float32), cv2_module.TM_CCOEFF_NORMED
        )
        score = float(result.max())
        if score > best_score:
            best_char, best_score = ch, score
    return best_char, best_score


def read_timestamp_overlay(
    region: np.ndarray, templates: TemplateSet, *, min_confidence: float = 0.6
) -> OcrResult:
    """Read the text in ``region`` — a grayscale crop of one recorder's
    OSD timestamp overlay, at the same scale ``templates`` was calibrated
    at — against ``templates``.

    A character whose best match scores below ``min_confidence`` is
    reported as ``"?"`` rather than the low-confidence guess itself —
    reporting a wrong-looking answer with its low score attached invites
    a caller to trust digits that should instead be treated as unread.

    Assumes ``region`` has the same total non-space character count as the
    reference the templates were calibrated from — true for a fixed-format
    OSD overlay reading the same field layout every frame, which is what
    every recorder's timestamp overlay actually is. A region containing an
    uncalibrated extra or missing character will have its literal spaces
    land at the calibrated position regardless, which no longer lines up
    with the real text; this shows up as an implausible parse failure in
    :func:`parse_recorder_timestamp` rather than a silent wrong read.
    """
    cv2 = _import_cv2()
    binary = _threshold(cv2, region)
    ranges = _drop_noise_segments(segment_characters(binary), templates.min_reference_width)
    if not ranges:
        return OcrResult(text="", confidence=0.0, per_char_confidence=())

    space_after = set(templates.space_positions)
    chars: list[str] = []
    confidences: list[float] = []
    for i, (x0, x1) in enumerate(ranges):
        ch, score = _recognize_one(cv2, binary[:, x0:x1], templates)
        confidences.append(max(score, 0.0))
        chars.append(ch if score >= min_confidence else "?")
        if (i + 1) in space_after:
            chars.append(" ")

    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(
        text="".join(chars), confidence=mean_confidence,
        per_char_confidence=tuple(confidences),
    )


#: Datetime formats seen in common consumer/commercial DVR OSD overlays.
#: Not exhaustive — a format this list doesn't cover simply fails to parse
#: rather than being silently misread as a different one.
COMMON_TIMESTAMP_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y.%m.%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%d.%m.%Y %H:%M:%S",
    "%m-%d-%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m.%d.%Y %H:%M:%S",
    "%Y-%m-%d %I:%M:%S %p",
)


def parse_recorder_timestamp(
    text: str, formats: tuple[str, ...] = COMMON_TIMESTAMP_FORMATS
) -> datetime | None:
    """The first format in ``formats`` that parses ``text`` exactly, or
    ``None`` if none does.

    Returns ``None`` rather than raising: a failed parse (an OCR result
    containing a ``"?"``, or a format this recorder doesn't use) is an
    ordinary, expected outcome for a caller to handle, not an exceptional
    one.
    """
    stripped = text.strip()
    for fmt in formats:
        try:
            # Deliberately naive: an OSD overlay carries no timezone
            # information at all, only the recorder's own local clock
            # reading -- attaching a tzinfo here would assert knowledge
            # this function does not have. Pairing this with an actual
            # UTC true-time anchor (see pramaan.timeline.clock) is where
            # that ambiguity gets resolved, not here.
            return datetime.strptime(stripped, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    return None
