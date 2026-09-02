"""Clip bookkeeping: recording, listing, and attaching a time range."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import ClipCreateRequest, ClipResponse, ClipTimeRangeUpdateRequest
from pramaan.case.store import Case, CaseError

router = APIRouter(tags=["clips"])


@router.post("/cases/{case_id}/clips", response_model=ClipResponse, status_code=201)
def add_clip(body: ClipCreateRequest, case: Case = Depends(get_case)) -> ClipResponse:
    try:
        clip = case.add_clip(
            body.evidence_item_id, channel=body.channel, kind=body.kind,
            start_offset=body.start_offset, end_offset=body.end_offset,
            start_time=body.start_time, end_time=body.end_time,
            first_sequence=body.first_sequence, last_sequence=body.last_sequence,
            frame_count=body.frame_count, sha256=body.sha256, format_id=body.format_id,
            note=body.note, actor=body.actor,
        )
    except CaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClipResponse.model_validate(clip)


@router.get("/cases/{case_id}/clips", response_model=list[ClipResponse])
def list_clips(
    case: Case = Depends(get_case),
    evidence_item_id: int | None = Query(default=None),
    channel: int | None = Query(default=None),
) -> list[ClipResponse]:
    clips = case.list_clips(evidence_item_id=evidence_item_id, channel=channel)
    return [ClipResponse.model_validate(clip) for clip in clips]


@router.patch("/cases/{case_id}/clips/{clip_id}/time-range", response_model=ClipResponse)
def set_clip_time_range(
    clip_id: int, body: ClipTimeRangeUpdateRequest, case: Case = Depends(get_case),
) -> ClipResponse:
    try:
        clip = case.set_clip_time_range(
            clip_id, body.start_time, body.end_time, actor=body.actor,
        )
    except CaseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ClipResponse.model_validate(clip)
