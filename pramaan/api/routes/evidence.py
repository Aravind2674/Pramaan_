"""Evidence item intake and lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import EvidenceItemCreateRequest, EvidenceItemResponse
from pramaan.case.store import Case, CaseError

router = APIRouter(tags=["evidence"])


@router.post("/cases/{case_id}/evidence", response_model=EvidenceItemResponse, status_code=201)
def add_evidence_item(
    body: EvidenceItemCreateRequest, case: Case = Depends(get_case),
) -> EvidenceItemResponse:
    item = case.add_evidence_item(
        description=body.description, source_path=body.source_path, sha256=body.sha256,
        size_bytes=body.size_bytes, device_type=body.device_type, make_model=body.make_model,
        serial_number=body.serial_number, acquired_at=body.acquired_at,
        write_block_attestation=body.write_block_attestation, actor=body.actor,
    )
    return EvidenceItemResponse.model_validate(item)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceItemResponse])
def list_evidence_items(case: Case = Depends(get_case)) -> list[EvidenceItemResponse]:
    return [EvidenceItemResponse.model_validate(item) for item in case.list_evidence_items()]


@router.get("/cases/{case_id}/evidence/{item_id}", response_model=EvidenceItemResponse)
def get_evidence_item(item_id: int, case: Case = Depends(get_case)) -> EvidenceItemResponse:
    try:
        item = case.get_evidence_item(item_id)
    except CaseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EvidenceItemResponse.model_validate(item)
