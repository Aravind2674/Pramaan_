const KIND_STYLES: Record<string, string> = {
  recorded: 'bg-kind-recorded/15 text-kind-recorded ring-kind-recorded/30',
  recovered: 'bg-kind-recovered/15 text-kind-recovered ring-kind-recovered/30',
  corrupt: 'bg-kind-corrupt/15 text-kind-corrupt ring-kind-corrupt/30',
  unknown: 'bg-kind-unknown/15 text-kind-unknown ring-kind-unknown/30',
}

const KIND_LABELS: Record<string, string> = {
  recorded: 'Recorded',
  recovered: 'Recovered',
  corrupt: 'Corrupt',
  unknown: 'Unknown',
}

/** A colored pill for a clip/segment `kind`. Falls back to the raw value
 * (styled neutrally) for any kind this UI doesn't specifically recognize,
 * rather than hiding or mislabeling it. */
export function KindBadge({ kind }: { kind: string }) {
  const style = KIND_STYLES[kind] ?? 'bg-surface-3 text-text-secondary ring-line-strong'
  const label = KIND_LABELS[kind] ?? kind
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {label}
    </span>
  )
}

type StatusTone = 'success' | 'danger' | 'neutral'

const STATUS_STYLES: Record<StatusTone, string> = {
  success: 'bg-success-soft text-success ring-success/30',
  danger: 'bg-danger-soft text-danger ring-danger/30',
  neutral: 'bg-surface-3 text-text-secondary ring-line-strong',
}

export function StatusBadge({ tone, children }: { tone: StatusTone; children: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${STATUS_STYLES[tone]}`}
    >
      {children}
    </span>
  )
}
