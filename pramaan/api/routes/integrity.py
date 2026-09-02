"""The case's audit-ledger chain verification."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import ChainVerificationResponse
from pramaan.case.store import Case

router = APIRouter(tags=["integrity"])


@router.get("/cases/{case_id}/integrity", response_model=ChainVerificationResponse)
def verify_integrity(case: Case = Depends(get_case)) -> ChainVerificationResponse:
    return ChainVerificationResponse.model_validate(case.verify_integrity())
