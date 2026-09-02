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
| Integrity | `pramaan.integrity` | **Implemented.** RFC 6962 Merkle tree with inclusion proofs over a case's artifact hashes; an append-only, hash-chained audit ledger with tamper localization; Ed25519 signing for an examiner's key. The BSA §63(4) certificate generator itself lives in `pramaan.report` and builds on this layer. 100% test coverage. |
| Timeline | `pramaan.timeline` | **Implemented.** Multi-channel timeline model over typed segments; gap/anomaly classification grounded in the Honeywell three-way deletion taxonomy (`docs/sources.md`); Theil-Sen clock-drift estimation, robust to a single bad anchor. 100% test coverage. |
| Analysis | `pramaan.analysis` | **Partially implemented, optional.** OSD timestamp reading via calibrated template matching (`osd_ocr`) — lazily imports OpenCV, needs the `analysis` extra, produces a recorder-claimed timestamp for pairing with an independently-verified true-time source, not evidence on its own. Detection/clustering not yet built. 100% test coverage. |
| Case store | `pramaan.case` | **Implemented.** One portable SQLite file per investigation; evidence items, recovered clips, and findings; every mutating action automatically recorded into the case's own integrity ledger; composes a `pramaan.timeline.Timeline` directly from stored clips. 100% test coverage. |
| Export | `pramaan.export` | **Implemented.** The Surveillance Evidence Format (SEF): a documented, versioned ZIP bundle with a manifest validated against a published JSON Schema, artifact hash/size verification, audit-ledger excerpts, and optional Ed25519 signing. Independently validatable without importing Pramaan. 100% test coverage. |
| Report | `pramaan.report` | **Implemented.** The BSA §63(4) certificate generator (`certificate.py`) — the statutory Part A / Part B admissibility certificate, with DVR named explicitly as a device category — and the narrative case report (`case_report.py`), composing case summary, evidence intake, recovery coverage, the clip exhibit list, examiner findings, timeline anomaly analysis, and audit-ledger integrity verification directly from a `pramaan.case.Case`. No commercial or open-source DVR forensic tool surveyed during this project's research generates either document. 100% test coverage. |
| API | `pramaan.api` | **Implemented.** A FastAPI service exposing case management, evidence and clip bookkeeping, examiner findings, the composed timeline, audit-ledger integrity verification, both report documents, and unsigned SEF export as one HTTP interface, backed by a `CaseWorkspace` that addresses cases by a URL-safe ID with path traversal made structurally impossible. Adds no forensic logic of its own — every route is a thin, tested translation onto the layers above it. 100% test coverage. |
| Examiner console (UI) | `web/` | **Implemented.** A React + TypeScript single-page app (Vite, TanStack Query, Tailwind CSS) driving `pramaan.api` end to end: case management, evidence and clip intake, the multi-channel timeline (a real SVG chart), examiner findings, audit-ledger integrity, and generating the certificate, the case report, and a SEF export bundle. Verified both with a Vitest suite and manually end to end against a live API. See `web/README.md`. |

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
├── recovery/       index walk, carving, unknown-vendor profiler
├── integrity/      Merkle tree, audit ledger, Ed25519 signing
├── timeline/       multi-channel timeline, gap/clock-drift analysis
├── analysis/       (optional) OSD timestamp reading; AI-assisted triage planned
├── case/           SQLite case store
├── export/         SEF interchange format
├── report/         BSA §63(4) certificate generator; narrative case report
└── api/            FastAPI backend -- case workspace, routes, schemas
web/                examiner console -- React + TypeScript + Vite frontend
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

### Frontend (`web/`)

Requires Node.js 22+. See [`web/README.md`](web/README.md) for the full
architecture and the API dev-server setup the frontend proxies to.

```bash
cd web
npm install
npm run dev
npm run test
npm run build
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
