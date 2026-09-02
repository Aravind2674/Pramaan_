import type { ReactNode } from 'react'
import { ApiError } from '../../api/errors'

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-text-secondary" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      {label}
    </div>
  )
}

/** Renders an unknown error as a readable banner -- an ApiError's own
 * server-supplied detail when available, a generic message otherwise.
 * Never swallows the error silently. */
export function ErrorBanner({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.detail : 'Something went wrong.'
  return (
    <div
      role="alert"
      className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"
    >
      {message}
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm text-text-muted">
      {children}
    </div>
  )
}
