# Pramaan

A multi-vendor DVR/NVR forensic acquisition, recovery, and analysis toolkit.

DVRs and NVRs do not store video on a filesystem any general-purpose
forensic tool understands — Hikvision, Dahua, and dozens of white-label
vendors each use an undocumented, proprietary on-disk layout. When a
recorder is seized as evidence today, an investigator's options are export
through the recorder's own menu (which cannot touch deleted footage and
loses metadata), or a closed, expensive, foreign commercial tool that may
not support the recorder in hand at all. Pramaan is an open, inspectable
alternative: acquire a seized disk read-only, identify and parse its
vendor's filesystem, recover footage whose index entry is gone, and produce
output built for a court — a documented interchange format and a
statutorily-formatted certificate — rather than just a video player.

This project is built for **SIH26150** (National Technical Research
Organisation, Smart India Hackathon 2026): *"Development of a Multi-Vendor
DVR/NVR Forensic Analysis Tool for Standardized Acquisition, Recovery, and
Analysis of Surveillance Evidence."*

## Status

This project is under active development. The table below is exact about
what exists today versus what is planned — nothing here is a placeholder or
a stub; a layer marked "planned" simply has no code yet.

| Layer | Package | Status |
|---|---|---|
| Acquisition | `pramaan.core` | **Implemented.** Read-only, bounds-checked disk image access with no write path at all; single-pass multi-algorithm hashing; write-block attestation. 100% test coverage. |
| Filesystem | `pramaan.fs` | **Implemented.** Declarative vendor-profile format and interpreter; vendor fingerprinting registry. Ships a fully-verified Dahua DHAV container profile and a deliberately partial Hikvision Master Sector profile (see `docs/sources.md` for exactly what is and isn't confirmed). 100% test coverage. |
| Recovery | `pramaan.recovery` | **Implemented.** Index-based clip extraction (generic across any profile with role-tagged fields); unallocated-space carving with a lossless remux and an independently-verified bit-exactness proof; the unknown-vendor structural profiler, promoted from a validated proof of concept into tested production code that also emits a loadable draft profile. 100% test coverage. |
| Integrity | `pramaan.integrity` | **Implemented.** RFC 6962 Merkle tree with inclusion proofs over a case's artifact hashes; an append-only, hash-chained audit ledger with tamper localization; Ed25519 signing for an examiner's key. The BSA §63(4) certificate generator itself lives in `pramaan.report` (planned) and builds on this layer. 100% test coverage. |
| Timeline | `pramaan.timeline` | **Implemented.** Multi-channel timeline model over typed segments; gap/anomaly classification grounded in the Honeywell three-way deletion taxonomy (`docs/sources.md`); Theil-Sen clock-drift estimation, robust to a single bad anchor. 100% test coverage. |
| Analysis | `pramaan.analysis` | **Partially implemented, optional.** OSD timestamp reading via calibrated template matching (`osd_ocr`) — lazily imports OpenCV, needs the `analysis` extra, produces a recorder-claimed timestamp for pairing with an independently-verified true-time source, not evidence on its own. Detection/clustering not yet built. 100% test coverage. |
| Case store | `pramaan.case` | **Implemented.** One portable SQLite file per investigation; evidence items, recovered clips, and findings; every mutating action automatically recorded into the case's own integrity ledger; composes a `pramaan.timeline.Timeline` directly from stored clips. 100% test coverage. |
| Export | `pramaan.export` | **Implemented.** The Surveillance Evidence Format (SEF): a documented, versioned ZIP bundle with a manifest validated against a published JSON Schema, artifact hash/size verification, audit-ledger excerpts, and optional Ed25519 signing. Independently validatable without importing Pramaan. 100% test coverage. |
| Report | `pramaan.report` | Planned — PDF reporting and the BSA §63(4) certificate generator. |
| API / examiner console | `pramaan.api`, `web/` | Planned. |

## Design principles

- **Evidence is never modified.** `DiskImage` has no write method — this is
  enforced by the type, not by convention.
- **A new vendor is a data change, not a code change.** Vendor filesystem
  layouts are declarative YAML validated against a JSON Schema; the
  interpreter that reads them does not change per vendor.
- **Nothing is claimed beyond what is verified.** A profile field's
  `status` (`confirmed`/`unconfirmed`) and a profile's overall `confidence`
  are load-bearing, not decorative — see `docs/sources.md`.
- **No cloud dependency, ever.** The core has no ML dependency and no
  network call in its evidence path; it installs and runs on an air-gapped
  machine.

## Repository layout

```
pramaan/
├── core/           acquisition — DiskImage, hashing, write-block attestation
├── fs/             filesystem — vendor profiles, the profile interpreter, fingerprinting
│   └── profiles/   *.yaml — one file per recorder filesystem/container format
├── recovery/       (planned) index walk, carving, unknown-vendor profiler
├── integrity/      (planned) audit ledger, statutory certificate
├── timeline/       (planned) multi-channel timeline, gap/clock analysis
├── analysis/       (planned, optional) AI-assisted investigative triage
├── case/           (planned) case store
├── export/         (planned) SEF interchange format
├── report/         (planned) PDF reporting
└── api/            (planned) FastAPI backend
web/                (planned) examiner console frontend
forge/              synthetic DVR image generator for testing (planned)
bench/              benchmark corpus and measured results (planned)
tests/
├── unit/
└── integration/
docs/
├── decisions/      architecture decision records
└── sources.md      citation log — every technical/legal claim traces here
scratch/            gitignored — throwaway/debug output only, never committed
```

## Development

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
pytest tests/ --cov=pramaan --cov-report=term-missing
ruff check pramaan/ tests/
mypy pramaan/
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
