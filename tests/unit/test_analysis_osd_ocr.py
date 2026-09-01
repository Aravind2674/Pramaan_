"""
Tests for pramaan.analysis.osd_ocr.

Skips entirely if OpenCV (the 'analysis' extra) isn't installed -- this
layer is optional by design, and its tests shouldn't fail a run that
correctly has none of it installed.

The synthetic-render helper below renders at one FIXED scale and baseline
for every string, deliberately -- this models what a real OSD overlay
actually does (draws at the same screen position and size in every frame
from the same recorder) and is the one thing that had to be gotten right
during development: an *adaptive* per-string render (crop to content,
rescale to a target height) silently drifts the effective scale between
different strings, which produces exactly the wrong-template-matching
failures a real, properly-calibrated OSD reader must never have.
"""

from __future__ import annotations

import builtins

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pramaan.analysis import osd_ocr as osd_ocr_module
from pramaan.analysis.osd_ocr import (
    COMMON_TIMESTAMP_FORMATS,
    OsdOcrError,
    build_templates_from_reference,
    parse_recorder_timestamp,
    read_timestamp_overlay,
    segment_characters,
)

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_SCALE = 1.5
_THICKNESS = 2
_BASELINE_Y = 40
_HEIGHT = 48


def render_strip(text: str) -> np.ndarray:
    """A synthetic OSD-style render at a fixed scale/baseline -- the
    calibration reference and every query in these tests use this exact
    same function, exactly matching how one real recorder's overlay is
    always drawn at one fixed size."""
    canvas = np.zeros((_HEIGHT, len(text) * 30 + 20), dtype=np.uint8)
    cv2.putText(canvas, text, (10, _BASELINE_Y), _FONT, _SCALE, 255, _THICKNESS, cv2.LINE_AA)
    xs = np.nonzero(canvas.any(axis=0))[0]
    x1 = int(xs.max()) + 5 if len(xs) else canvas.shape[1]
    return canvas[:, :x1]


# A real recorder has exactly one fixed OSD format; calibration reflects
# that -- each (format, reference-instance-of-that-format) pair below
# stands in for one recorder, calibrated once from one labeled crop of its
# own overlay, then tested against a DIFFERENT instance of that same
# format (proving recognition, not recall of the calibration string
# itself). Testing several different *formats* against one shared
# calibration would not correspond to anything a real deployment does --
# one recorder does not switch its space position between reads.
REFERENCE_TEXT = "0123456789-45:30/12.07"
REFERENCE_STRIP = render_strip(REFERENCE_TEXT)

# Each reference is chosen to contain every digit 0-9 at least once (in
# addition to matching its query's delimiter shape) -- a digit genuinely
# absent from calibration has no template and correctly reads back as "?",
# which is the right behavior, not a bug, so the test data must not
# accidentally exercise that case by omission.
FORMAT_CASES = [
    ("2026-03-14 21:48:49", "1234-56-78 90:12:34"),
    ("09/17/2025 03:05:11", "01/23/4567 89:01:23"),
    ("12.31.2026-23:59:59", "01.23.4567-89:01:23"),
    ("2001-01-01 00:00:00", "3456-78-90 12:34:56"),
]


def _templates(reference_text: str = REFERENCE_TEXT):
    return build_templates_from_reference(render_strip(reference_text), reference_text)


@pytest.mark.parametrize(("query_text", "reference_text"), FORMAT_CASES)
def test_round_trip_reads_the_rendered_timestamp_exactly(query_text, reference_text):
    templates = _templates(reference_text)
    strip = render_strip(query_text)
    result = read_timestamp_overlay(strip, templates)

    assert result.text == query_text
    assert result.confidence > 0.9
    assert all(c > 0.9 for c in result.per_char_confidence)


def test_result_parses_into_the_expected_datetime():
    templates = _templates("1234-56-78 90:12:34")
    strip = render_strip("2026-03-14 21:48:49")
    result = read_timestamp_overlay(strip, templates)
    parsed = parse_recorder_timestamp(result.text)
    assert parsed is not None
    assert parsed.isoformat() == "2026-03-14T21:48:49"


def test_mismatched_reference_text_length_raises():
    with pytest.raises(OsdOcrError):
        build_templates_from_reference(REFERENCE_STRIP, "too short")


def test_reference_text_with_wrong_character_count_raises():
    # Same visual content, but a deliberately wrong transcription length.
    with pytest.raises(OsdOcrError):
        build_templates_from_reference(REFERENCE_STRIP, REFERENCE_TEXT + "999")


def test_unrecognized_character_reads_as_question_mark():
    """A character never seen during calibration must not be guessed at
    -- letters were never in the reference set at all."""
    templates = _templates()
    strip = render_strip("2026-03-14 21:48:49X")  # trailing char has no template
    result = read_timestamp_overlay(strip, templates)
    assert result.text.endswith("?")


def test_low_confidence_glyph_is_reported_as_question_mark_not_a_guess():
    templates = _templates()
    rng = np.random.default_rng(7)
    noise_glyph = (rng.random((_HEIGHT, 20)) > 0.5).astype(np.uint8) * 255
    strip = np.zeros((_HEIGHT, 40), dtype=np.uint8)
    strip[:, 10:30] = noise_glyph
    result = read_timestamp_overlay(strip, templates, min_confidence=0.9)
    assert "?" in result.text


def test_empty_region_returns_empty_result():
    blank = np.zeros((_HEIGHT, 100), dtype=np.uint8)
    result = read_timestamp_overlay(blank, _templates())
    assert result.text == ""
    assert result.confidence == 0.0
    assert result.per_char_confidence == ()


def test_segment_characters_handles_ink_running_to_the_last_column():
    """A strip with no trailing blank margin after the final character's
    ink -- the run never closes via a gap, only via reaching the end of
    the array -- must still be reported as a segment, not dropped."""
    strip = np.zeros((10, 6), dtype=np.uint8)
    strip[:, 4:6] = 255  # ink reaches all the way to the last column
    ranges = segment_characters(strip)
    assert ranges == [(4, 6)]


def test_segment_characters_ignores_literal_spaces():
    strip = render_strip("12 34")
    ranges = segment_characters(strip)
    assert len(ranges) == 4  # "1","2","3","4" -- the space contributes no ink run


def test_noise_speckle_in_a_space_is_dropped_as_too_narrow_to_be_a_character():
    """A single stray bright pixel or thin artifact in what should be a
    blank gap must not be promoted to a spurious low-confidence character
    -- it should be filtered out by the minimum-width check before
    recognition is even attempted."""
    strip = render_strip("2026-03-14 21:48:49").copy()
    # Inject a single-column speckle into the middle of the space gap.
    ranges = segment_characters(strip)
    gap_start = ranges[3][1] + 2  # a couple of columns into the post-"6" gap
    strip[20:22, gap_start] = 255

    templates = _templates("1234-56-78 90:12:34")
    result = read_timestamp_overlay(strip, templates)
    assert result.text == "2026-03-14 21:48:49"


@pytest.mark.parametrize("fmt", COMMON_TIMESTAMP_FORMATS)
def test_parse_recorder_timestamp_covers_every_declared_format(fmt):
    from datetime import datetime

    sample = datetime(2026, 3, 14, 21, 48, 49)  # noqa: DTZ001 -- OSD overlays carry no tz info
    text = sample.strftime(fmt)
    parsed = parse_recorder_timestamp(text)
    assert parsed is not None
    assert parsed.hour == 21 and parsed.minute == 48 and parsed.second == 49


def test_parse_recorder_timestamp_returns_none_for_unparseable_text():
    assert parse_recorder_timestamp("not a timestamp") is None
    assert parse_recorder_timestamp("2026-03-1?:21:48:49") is None
    assert parse_recorder_timestamp("") is None


def test_parse_recorder_timestamp_respects_custom_format_list():
    assert parse_recorder_timestamp("14|03|2026", formats=("%d|%m|%Y",)) is not None
    assert parse_recorder_timestamp("14|03|2026", formats=("%Y-%m-%d",)) is None


def test_import_cv2_error_wraps_a_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("simulated: opencv not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(OsdOcrError, match="analysis"):
        osd_ocr_module._import_cv2()
