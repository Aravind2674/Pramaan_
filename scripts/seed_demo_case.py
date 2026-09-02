#!/usr/bin/env python
"""
Populate a Pramaan case workspace with a synthetic demonstration case,
so the API and UI have something realistic to show instead of an empty
workspace. See :mod:`pramaan.demo` for exactly what "synthetic" means
here and what it deliberately doesn't claim to be.

Usage:

    python scripts/seed_demo_case.py --workspace ./demo-workspace
    python scripts/seed_demo_case.py --workspace ./demo-workspace --force

``--force`` removes an existing case at the same ID (and its ledger)
before re-seeding -- safe here specifically because this script only
ever touches its own synthetic demo case, never a real one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pramaan.api.workspace import CaseWorkspace, WorkspaceError
from pramaan.demo import DEFAULT_CASE_ID, seed_demo_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--workspace", type=Path, default=Path("demo-workspace"),
        help="Directory to hold the case workspace (created if missing). Default: ./demo-workspace",
    )
    parser.add_argument(
        "--case-id", default=DEFAULT_CASE_ID,
        help=f"Case ID to seed. Default: {DEFAULT_CASE_ID}",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Remove an existing case at --case-id (and its ledger) before seeding.",
    )
    args = parser.parse_args(argv)

    workspace = CaseWorkspace(args.workspace)

    if args.force:
        case_path = workspace.root / f"{args.case_id}.case"
        ledger_path = workspace.root / f"{args.case_id}.case.ledger.jsonl"
        for path in (case_path, ledger_path):
            path.unlink(missing_ok=True)

    try:
        result = seed_demo_case(workspace, case_id=args.case_id)
    except WorkspaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("hint: pass --force to replace an existing demo case at this ID.", file=sys.stderr)
        return 1

    verification = result.case.verify_integrity()
    result.case.close()

    print(f"Seeded case {args.case_id!r} in {args.workspace}")
    print(f"  Evidence items: {len(result.evidence_item_ids)}")
    print(f"  Clips:          {len(result.clips)}")
    print(f"  Findings:       {len(result.finding_ids)}")
    print(f"  Ledger chain:   {'VALID' if verification.valid else 'BROKEN -- ' + str(verification.reason)}")
    print()
    print("Start the API against this workspace, e.g.:")
    print(
        "  python -c \"import uvicorn; from pramaan.api.app import create_app; "
        f"uvicorn.run(create_app({str(args.workspace)!r}), host='127.0.0.1', port=8000)\""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
