"""
Shared reportlab paragraph styles for every document :mod:`pramaan.report`
renders.

Factored out once :mod:`pramaan.report.certificate` and
:mod:`pramaan.report.case_report` both needed the exact same
title/subtitle/heading/body/mono/small style set — duplicating the same
five ``ParagraphStyle`` constructions across two files would just mean the
same visual theme silently drifting apart the first time only one of them
got edited.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm


def build_report_styles() -> dict[str, ParagraphStyle]:
    """The common style set every :mod:`pramaan.report` document builds
    its story from: ``title``, ``subtitle``, ``heading``, ``body``,
    ``mono`` (for hashes and other fixed-width values), and ``small``
    (for disclaimers and footnotes)."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontSize=15, spaceAfter=2 * mm),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Heading3"], fontSize=11, textColor=colors.grey),
        "heading": ParagraphStyle(
            "ReportHeading", parent=base["Heading2"], fontSize=13, spaceBefore=6 * mm, spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=10, leading=14),
        "mono": ParagraphStyle("ReportMono", parent=base["BodyText"], fontName="Courier", fontSize=9, leading=13),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontSize=8, textColor=colors.grey, leading=11),
    }
