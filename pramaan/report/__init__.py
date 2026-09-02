"""
Report layer — the court-facing output everything else has been building
toward.

:mod:`pramaan.report.certificate` renders the Bharatiya Sakshya Adhiniyam
2023 Section 63(4) certificate — Part A (the device custodian) and Part B
(a technical expert), each with the hash-algorithm declaration the
Schedule itself asks for. No tool surveyed during this project's research
(see ``docs/sources.md``) generates this; every one of them stops at a
generic export report. :mod:`pramaan.report.case_report` (planned) is the
full narrative case report this certificate accompanies.
"""

from pramaan.report.certificate import (
    Certificate,
    CertificateError,
    CertificatePartA,
    CertificatePartB,
    DeviceDetails,
    HashDeclaration,
    generate_certificate_pdf,
)

__all__ = [
    "Certificate",
    "CertificateError",
    "CertificatePartA",
    "CertificatePartB",
    "DeviceDetails",
    "HashDeclaration",
    "generate_certificate_pdf",
]
