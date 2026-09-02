"""Case creation, lookup, and listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pramaan.api.dependencies import get_case, get_workspace
from pramaan.api.schemas import CaseCreateRequest, CaseInfoResponse
from pramaan.api.workspace import CaseWorkspace, WorkspaceError
from pramaan.case.store import Case

router = APIRouter(tags=["cases"])


@router.post("/cases", response_model=CaseInfoResponse, status_code=201)
def create_case(body: CaseCreateRequest, workspace: CaseWorkspace = Depends(get_workspace)) -> CaseInfoResponse:
    try:
        case = workspace.create_case(
            body.case_id, title=body.title,
            investigating_agency=body.investigating_agency, examiner_name=body.examiner_name,
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        return CaseInfoResponse.model_validate(case.info())
    finally:
        case.close()


@router.get("/cases", response_model=list[str])
def list_cases(workspace: CaseWorkspace = Depends(get_workspace)) -> list[str]:
    return workspace.list_case_ids()


@router.get("/cases/{case_id}", response_model=CaseInfoResponse)
def get_case_info(case: Case = Depends(get_case)) -> CaseInfoResponse:
    return CaseInfoResponse.model_validate(case.info())
