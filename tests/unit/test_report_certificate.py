"""
Tests for pramaan.report.certificate.

Uses pypdf (dev-only, never a runtime dependency of pramaan.report) to
extract text back out of generated PDFs — proving the certificate actually
contains the fields it was given, not just that a nonzero-size file exists.
"""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from pramaan.report.certificate import (
    DEVICE_TYPES,
    HASH_ALGORITHMS,
    Certificate,
    CertificateError,
    CertificatePartA,
    CertificatePartB,
    DeviceDetails,
    HashDeclaration,
    generate_certificate_pdf,
)


def _device(**overrides) -> DeviceDetails:
    kwargs = {
        "device_type": "DVR",
        "make_and_model": "Dahua XVR5108HS",
        "serial_number": "SN123456",
        "identifier": None,
    }
    kwargs.update(overrides)
    return DeviceDetails(**kwargs)


def _hash(**overrides) -> HashDeclaration:
    kwargs = {"algorithm": "SHA256", "value": "a" * 64}
    kwargs.update(overrides)
    return HashDeclaration(**kwargs)


def _part_a(**overrides) -> CertificatePartA:
    kwargs = {
        "custodian_name": "Inspector R. Kumar",
        "custodian_address": "Cyber Cell, City Police HQ",
        "device": _device(),
        "lawful_control_declared": True,
        "functioning_properly_declared": True,
        "hash": _hash(),
        "place": "Chennai",
        "date": "2026-09-02",
        "time_ist": "14:32",
    }
    kwargs.update(overrides)
    return CertificatePartA(**kwargs)


def _part_b(**overrides) -> CertificatePartB:
    kwargs = {
        "expert_name": "Dr. A. Examiner",
        "expert_designation": "Digital Forensic Examiner, Pramaan Team",
        "device": _device(),
        "hash": _hash(),
        "technical_statement": "The device was imaged read-only via a hardware write-blocker.",
        "place": "Chennai",
        "date": "2026-09-02",
        "time_ist": "15:10",
    }
    kwargs.update(overrides)
    return CertificatePartB(**kwargs)


def _certificate(**overrides) -> Certificate:
    kwargs = {"case_id": "SIH26150-001", "part_a": _part_a(), "part_b": _part_b()}
    kwargs.update(overrides)
    return Certificate(**kwargs)


def _extract_text(path) -> str:
    return " ".join(page.extract_text() for page in PdfReader(path).pages)


# ---------------------------------------------------------------------------
# Data model validation
# ---------------------------------------------------------------------------

def test_device_details_rejects_unknown_type():
    with pytest.raises(CertificateError):
        DeviceDetails(device_type="Toaster", make_and_model="x")


def test_device_details_other_type_requires_other_device_type():
    with pytest.raises(CertificateError):
        DeviceDetails(device_type="Other", make_and_model="x")
    # Should not raise when supplied:
    DeviceDetails(device_type="Other", make_and_model="x", other_device_type="Custom NVR")


def test_device_details_display_type_uses_other_value():
    device = DeviceDetails(device_type="Other", make_and_model="x", other_device_type="Embedded recorder")
    assert device.display_type == "Embedded recorder"


def test_device_details_display_type_for_named_category():
    assert _device().display_type == "DVR"


def test_hash_declaration_rejects_unknown_algorithm():
    with pytest.raises(CertificateError):
        HashDeclaration(algorithm="CRC32", value="abc")


def test_hash_declaration_other_requires_name():
    with pytest.raises(CertificateError):
        HashDeclaration(algorithm="Other", value="abc")
    HashDeclaration(algorithm="Other", value="abc", other_algorithm_name="BLAKE2b")


def test_hash_declaration_rejects_empty_value():
    with pytest.raises(CertificateError):
        HashDeclaration(algorithm="SHA256", value="   ")


def test_hash_declaration_display_algorithm():
    assert _hash().display_algorithm == "SHA256"
    other = HashDeclaration(algorithm="Other", value="x", other_algorithm_name="BLAKE2b")
    assert other.display_algorithm == "BLAKE2b"


def test_part_a_requires_both_declarations():
    with pytest.raises(CertificateError):
        _part_a(lawful_control_declared=False)
    with pytest.raises(CertificateError):
        _part_a(functioning_properly_declared=False)


def test_part_b_requires_nonempty_technical_statement():
    with pytest.raises(CertificateError):
        _part_b(technical_statement="   ")


def test_all_device_types_are_accepted_except_other_without_a_name():
    for device_type in DEVICE_TYPES:
        if device_type == "Other":
            continue
        DeviceDetails(device_type=device_type, make_and_model="x")


def test_all_hash_algorithms_are_accepted_except_other_without_a_name():
    for algorithm in HASH_ALGORITHMS:
        if algorithm == "Other":
            continue
        HashDeclaration(algorithm=algorithm, value="somehash")


# ---------------------------------------------------------------------------
# PDF generation and content
# ---------------------------------------------------------------------------

def test_generate_creates_a_pdf_file(tmp_path):
    dest = tmp_path / "cert.pdf"
    result = generate_certificate_pdf(_certificate(), dest)
    assert result == dest
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_generate_raises_if_destination_already_exists(tmp_path):
    dest = tmp_path / "cert.pdf"
    dest.write_bytes(b"already here")
    with pytest.raises(CertificateError):
        generate_certificate_pdf(_certificate(), dest)


def test_pdf_is_a_valid_pdf_with_two_pages(tmp_path):
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(_certificate(), dest)
    reader = PdfReader(dest)
    assert len(reader.pages) == 2


def test_pdf_contains_case_id_and_both_parts(tmp_path):
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(_certificate(case_id="MY-CASE-999"), dest)
    text = _extract_text(dest)
    assert "MY-CASE-999" in text
    assert "Part A" in text
    assert "Part B" in text
    assert "Bharatiya Sakshya Adhiniyam, 2023" in text


def test_pdf_contains_custodian_and_expert_names(tmp_path):
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(
        _certificate(
            part_a=_part_a(custodian_name="Custodian Name Unique"),
            part_b=_part_b(expert_name="Expert Name Unique"),
        ),
        dest,
    )
    text = _extract_text(dest)
    assert "Custodian Name Unique" in text
    assert "Expert Name Unique" in text


def test_pdf_contains_device_type_dvr(tmp_path):
    """DVR is the specific, named category this whole project is built
    around -- it must actually appear in the rendered document, not just
    exist in the data model."""
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(_certificate(), dest)
    text = _extract_text(dest)
    assert "DVR" in text


def test_pdf_contains_the_hash_value(tmp_path):
    dest = tmp_path / "cert.pdf"
    distinctive_hash = "deadbeef" * 8
    generate_certificate_pdf(_certificate(part_a=_part_a(hash=_hash(value=distinctive_hash))), dest)
    text = _extract_text(dest)
    assert distinctive_hash in text


def test_pdf_marks_the_selected_hash_algorithm_and_not_others(tmp_path):
    dest = tmp_path / "cert.pdf"
    md5_hash = _hash(algorithm="MD5")
    generate_certificate_pdf(
        _certificate(part_a=_part_a(hash=md5_hash), part_b=_part_b(hash=md5_hash)), dest,
    )
    text = _extract_text(dest)
    assert "[X] MD5" in text
    assert "[X] SHA256" not in text
    assert "[X] SHA1" not in text


def test_pdf_contains_technical_statement(tmp_path):
    dest = tmp_path / "cert.pdf"
    distinctive_statement = "A wholly distinctive technical statement for this test."
    generate_certificate_pdf(
        _certificate(part_b=_part_b(technical_statement=distinctive_statement)), dest,
    )
    text = _extract_text(dest)
    assert distinctive_statement in text


def test_pdf_contains_disclaimer_about_verifying_the_primary_source(tmp_path):
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(_certificate(), dest)
    text = _extract_text(dest)
    assert "indiacode.nic.in" in text


def test_pdf_text_has_no_unicode_replacement_characters(tmp_path):
    """A legal document rendering a broken glyph is a real defect, not a
    cosmetic one -- this failed once during development (an em dash that
    round-tripped as U+FFFD) and is worth guarding against permanently."""
    dest = tmp_path / "cert.pdf"
    generate_certificate_pdf(_certificate(), dest)
    text = _extract_text(dest)
    assert "�" not in text


def test_pdf_shows_na_for_missing_optional_device_fields(tmp_path):
    dest = tmp_path / "cert.pdf"
    device = DeviceDetails(device_type="DVR", make_and_model="Generic DVR")
    generate_certificate_pdf(
        _certificate(part_a=_part_a(device=device), part_b=_part_b(device=device)), dest,
    )
    text = _extract_text(dest)
    assert "N/A" in text


def test_pdf_with_other_device_type_shows_the_custom_name(tmp_path):
    dest = tmp_path / "cert.pdf"
    device = DeviceDetails(device_type="Other", make_and_model="x", other_device_type="Bespoke Recorder XYZ")
    generate_certificate_pdf(
        _certificate(part_a=_part_a(device=device), part_b=_part_b(device=device)), dest,
    )
    text = _extract_text(dest)
    assert "Bespoke Recorder XYZ" in text
