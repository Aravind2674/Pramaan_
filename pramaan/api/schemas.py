"""
Pydantic request and response models for the API layer.

Every response model sets ``model_config = ConfigDict(from_attributes=True)``
so it can be constructed directly from the already-tested dataclasses
:mod:`pramaan.case.store`, :mod:`pramaan.timeline.model`, and
:mod:`pramaan.integrity.ledger` return — this layer re-declares their
shape for the OpenAPI schema and HTTP serialization, it does not
re-implement or duplicate their logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

class CaseCreateRequest(BaseModel):
    case_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1)
    investigating_agency: str = Field(..., min_length=1)
    examiner_name: str = Field(..., min_length=1)


class CaseInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    title: str
    investigating_agency: str
    examiner_name: str
    created_at: str


# ---------------------------------------------------------------------------
# Evidence items
# ---------------------------------------------------------------------------

class EvidenceItemCreateRequest(BaseModel):
    description: str = Field(..., min_length=1)
    source_path: str = Field(..., min_length=1)
    sha256: str = Field(..., min_length=1)
    size_bytes: int = Field(..., ge=0)
    device_type: str | None = None
    make_model: str | None = None
    serial_number: str | None = None
    acquired_at: str | None = None
    write_block_attestation: dict[str, Any] | None = None
    actor: str | None = None


class EvidenceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    device_type: str | None
    make_model: str | None
    serial_number: str | None
    source_path: str
    sha256: str
    size_bytes: int
    acquired_at: str
    write_block_attestation: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------

class ClipCreateRequest(BaseModel):
    evidence_item_id: int
    channel: int = Field(..., ge=0)
    kind: str
    start_offset: int | None = None
    end_offset: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    first_sequence: int | None = None
    last_sequence: int | None = None
    frame_count: int | None = None
    sha256: str | None = None
    format_id: str | None = None
    note: str = ""
    actor: str | None = None


class ClipTimeRangeUpdateRequest(BaseModel):
    start_time: str
    end_time: str
    actor: str | None = None


class ClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_item_id: int
    channel: int
    kind: str
    start_offset: int | None
    end_offset: int | None
    start_time: str | None
    end_time: str | None
    first_sequence: int | None
    last_sequence: int | None
    frame_count: int | None
    sha256: str | None
    format_id: str | None
    note: str


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class FindingCreateRequest(BaseModel):
    author: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    clip_id: int | None = None
    created_at: str | None = None


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: str
    author: str
    clip_id: int | None
    category: str
    description: str


# ---------------------------------------------------------------------------
# Timeline and integrity
# ---------------------------------------------------------------------------

class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: int
    start: datetime
    end: datetime
    kind: str
    first_sequence: int | None
    last_sequence: int | None
    note: str


class TimelineResponse(BaseModel):
    segments: list[SegmentResponse]


class ChainVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid: bool
    break_at_index: int | None
    reason: str | None


# ---------------------------------------------------------------------------
# Reports: the Section 63(4) certificate
# ---------------------------------------------------------------------------

class DeviceDetailsRequest(BaseModel):
    device_type: str
    make_and_model: str
    serial_number: str | None = None
    identifier: str | None = None
    other_device_type: str | None = None


class HashDeclarationRequest(BaseModel):
    algorithm: str
    value: str
    other_algorithm_name: str | None = None


class CertificatePartARequest(BaseModel):
    custodian_name: str
    custodian_address: str
    device: DeviceDetailsRequest
    lawful_control_declared: bool
    functioning_properly_declared: bool
    hash: HashDeclarationRequest
    place: str
    date: str
    time_ist: str


class CertificatePartBRequest(BaseModel):
    expert_name: str
    expert_designation: str
    device: DeviceDetailsRequest
    hash: HashDeclarationRequest
    technical_statement: str
    place: str
    date: str
    time_ist: str


class CertificateGenerateRequest(BaseModel):
    part_a: CertificatePartARequest
    part_b: CertificatePartBRequest


# ---------------------------------------------------------------------------
# Reports: the narrative case report
# ---------------------------------------------------------------------------

class GapAnalysisWindowRequest(BaseModel):
    start: datetime
    end: datetime


class CaseReportGenerateRequest(BaseModel):
    gap_analysis_window: GapAnalysisWindowRequest | None = None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ArtifactSpecRequest(BaseModel):
    artifact_id: str = Field(..., min_length=1)
    source_path: str = Field(..., min_length=1)
    description: str = ""


class ExportBuildRequest(BaseModel):
    artifacts: list[ArtifactSpecRequest] = Field(default_factory=list)
    include_ledger: bool = True
