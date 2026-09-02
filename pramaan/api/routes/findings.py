"""Examiner findings: recording and listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import FindingCreateRequest, FindingResponse
from pramaan.case.store import Case, CaseError

router = APIRouter(tags=["findings"])


@router.post("/cases/{case_id}/findings", response_model=FindingResponse, status_code=201)
def add_finding(body: FindingCreateRequest, case: Case = Depends(get_case)) -> FindingResponse:
    try:
        finding = case.add_finding(
            author=body.author, category=body.category, description=body.description,
            clip_id=body.clip_id, created_at=body.created_at,
        )
    except CaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FindingResponse.model_validate(finding)


@router.get("/cases/{case_id}/findings", response_model=list[FindingResponse])
def list_findings(case: Case = Depends(get_case)) -> list[FindingResponse]:
    return [FindingResponse.model_validate(f) for f in case.list_findings()]
