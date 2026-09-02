"""
Export layer — the Surveillance Evidence Format (SEF).

A SEF bundle is a documented, versioned ZIP: a manifest (validated against
``sef_manifest.schema.json``, published in this package so a third party
can validate a bundle without importing Pramaan at all), the artifacts it
describes, and an excerpt of the case's audit ledger. This is Pramaan's
answer to the "standardized" half of the problem statement's title — a
vendor-neutral interchange format an investigator can hand to another
agency, another tool, or a court, and have its contents independently
checkable rather than trusted on Pramaan's say-so.
"""

from pramaan.export.sef import (
    SEF_FORMAT_VERSION,
    ArtifactSpec,
    SefError,
    ValidationResult,
    build_sef_bundle,
    read_manifest,
    validate_sef_bundle,
)

__all__ = [
    "SEF_FORMAT_VERSION",
    "ArtifactSpec",
    "SefError",
    "ValidationResult",
    "build_sef_bundle",
    "read_manifest",
    "validate_sef_bundle",
]
