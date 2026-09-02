import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface AppShellProps {
  children: ReactNode
}

/** The top-level frame every page renders inside: branding, top nav, and
 * a constrained content area. There is no sidebar or per-case nav here --
 * that lives in CaseDetailPage, scoped to the case actually being worked. */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-surface-0">
      <header className="border-b border-line bg-surface-1 shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-center gap-2 text-text-primary">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-strong text-sm font-bold text-white">
              P
            </span>
            <span className="text-base font-semibold tracking-tight">Pramaan</span>
          </Link>
          <span className="text-xs text-text-muted">DVR / NVR forensic analysis</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
