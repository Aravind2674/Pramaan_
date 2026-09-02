"""Every route module the API layer exposes, aggregated into one router."""

from fastapi import APIRouter

from pramaan.api.routes.cases import router as cases_router
from pramaan.api.routes.clips import router as clips_router
from pramaan.api.routes.evidence import router as evidence_router
from pramaan.api.routes.export import router as export_router
from pramaan.api.routes.findings import router as findings_router
from pramaan.api.routes.integrity import router as integrity_router
from pramaan.api.routes.reports import router as reports_router
from pramaan.api.routes.timeline import router as timeline_router

api_router = APIRouter()
api_router.include_router(cases_router)
api_router.include_router(evidence_router)
api_router.include_router(clips_router)
api_router.include_router(findings_router)
api_router.include_router(timeline_router)
api_router.include_router(integrity_router)
api_router.include_router(reports_router)
api_router.include_router(export_router)

__all__ = ["api_router"]
