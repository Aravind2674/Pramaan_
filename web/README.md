# Pramaan — examiner console

The web frontend for Pramaan: a React + TypeScript single-page app that
drives `pramaan.api` (see `../pramaan/api/`) end to end -- case creation,
evidence and clip intake, the composed multi-channel timeline, examiner
findings, audit-ledger integrity, and generating the Section 63(4)
certificate, the narrative case report, and a SEF export bundle.

Every page here talks to a real running `pramaan.api` instance. There is
no mock data and no placeholder screen -- an empty state (no cases yet,
no clips recorded) is rendered honestly as an empty state, not hidden or
faked.

## Stack

- **React 19 + TypeScript** (strict mode, `noUncheckedIndexedAccess`), built with **Vite**.
- **React Router** for client-side routing (case list → new case → per-case tabs).
- **TanStack Query** for server state -- every list, detail, and mutation goes through it, so loading/error/race-condition handling isn't hand-rolled per page.
- **Tailwind CSS v4** for styling, themed once in `src/index.css` via a single `@theme` token set (see below) -- no component reaches for a raw hex color.
- **Vitest + React Testing Library** for tests.
- **oxlint** for linting.
- System fonts only, no external font or icon CDN: this is a forensic tool an examiner may need to run on an air-gapped machine, the same reasoning `pramaan.core`'s acquisition layer is built around.

## Running it

```bash
npm install
npm run dev
```

The dev server proxies `/api/*` to `http://127.0.0.1:8000` (see
`vite.config.ts`), so run the API alongside it:

```bash
# from the repository root, with pramaan installed
python -m uvicorn pramaan.api.app:create_app --factory --reload \
  --app-dir . --port 8000
```

(`create_app` takes a workspace directory; adjust the factory call or
write a two-line launcher script if you want a fixed workspace path
instead of relying on `create_app`'s default.)

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Start the Vite dev server with the `/api` proxy. |
| `npm run build` | Type-check (`tsc -b`) then production-build with Vite. |
| `npm run lint` | Run oxlint. |
| `npm run test` | Run the Vitest suite once. |
| `npm run test:coverage` | Run the suite with coverage. |
| `npm run preview` | Serve the production build locally. |

## Theme

A single light theme, not a light/dark toggle -- committing to one
theme actually built and tested beats a half-built toggle nobody
verified both sides of. Every color, font, and surface token lives in
`src/index.css`'s `@theme` block; components use the generated Tailwind
utilities (`bg-surface-1`, `text-text-secondary`, `border-line`, …)
rather than one-off values, so the whole app's palette can be re-tuned
from one file.

## Structure

```
src/
├── api/          typed fetch client + hand-written mirrors of pramaan.api.schemas
├── components/
│   ├── layout/   AppShell (the one page frame every route renders inside)
│   ├── ui/       Card, Badge, form fields, spinner/error/empty states
│   ├── forms/    multi-field groups shared across more than one page (device + hash)
│   └── timeline/ the SVG multi-channel timeline chart
├── hooks/        TanStack Query hooks (one per pramaan.api resource) + query-key registry
├── lib/          pure helpers: date/byte/duration formatting, file-download
└── pages/
    ├── CaseListPage.tsx, NewCasePage.tsx
    ├── CaseDetailPage.tsx      the per-case tab shell
    └── case/                   one file per tab (Overview, Evidence, Clips, Timeline,
                                 Findings, Integrity, Reports, Export)
```

## What's out of scope, deliberately

- **Acquisition and recovery are not driven from the UI.** `pramaan.core`
  and `pramaan.recovery` work against raw disk images and container
  files on the examiner's machine; the API layer records their *results*
  (evidence items, clips) rather than triggering acquisition itself, and
  the UI follows that boundary.
- **SEF export is unsigned from this UI**, matching `pramaan.api`'s own
  export endpoint -- see `docs/decisions/0010-api-layer.md`.
