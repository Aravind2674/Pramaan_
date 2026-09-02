"""
SEF bundle export.

Signing is out of scope for this endpoint deliberately, not by
oversight: :func:`pramaan.export.sef.build_sef_bundle` accepts an
``Ed25519PrivateKey`` directly, and there is no key-management endpoint
in this API layer yet to hold or reference one safely over HTTP. This
endpoint builds an unsigned bundle -- every hash, ledger-chain check, and
manifest-schema guarantee `pramaan.export` provides still applies; a
caller who needs a signed bundle uses ``pramaan.export.sef`` directly
with their own key material until a dedicated signing endpoint exists.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response

from pramaan.api.dependencies import get_case
from pramaan.api.schemas import ExportBuildRequest
from pramaan.case.store import Case
from pramaan.export.sef import ArtifactSpec, SefError, build_sef_bundle

router = APIRouter(tags=["export"])


@router.post("/cases/{case_id}/export")
def export_case(body: ExportBuildRequest, case: Case = Depends(get_case)) -> Response:
    info = case.info()
    artifacts = [
        ArtifactSpec(
            artifact_id=spec.artifact_id, source_path=Path(spec.source_path),
            description=spec.description,
        )
        for spec in body.artifacts
    ]
    ledger_entries = case.ledger.entries if body.include_ledger else ()

    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = Path(tmp_dir) / "bundle.sef.zip"
        try:
            build_sef_bundle(
                dest, case_id=info.case_id, title=info.title,
                investigating_agency=info.investigating_agency, examiner_name=info.examiner_name,
                artifacts=artifacts, ledger_entries=ledger_entries,
                ledger_head_hash=case.ledger.head_hash,
            )
        except SefError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        bundle_bytes = dest.read_bytes()

    return Response(
        content=bundle_bytes, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{info.case_id}.sef.zip"'},
    )
