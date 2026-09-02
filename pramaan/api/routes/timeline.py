"""The case's composed multi-channel timeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import SegmentResponse, TimelineResponse
from pramaan.case.store import Case

router = APIRouter(tags=["timeline"])


@router.get("/cases/{case_id}/timeline", response_model=TimelineResponse)
def get_timeline(case: Case = Depends(get_case)) -> TimelineResponse:
    timeline = case.build_timeline()
    return TimelineResponse(
        segments=[SegmentResponse.model_validate(s) for s in timeline.segments],
    )
