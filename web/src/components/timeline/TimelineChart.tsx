import type { Segment } from '../../api/types'

const KIND_FILL: Record<string, string> = {
  recorded: 'var(--color-kind-recorded)',
  recovered: 'var(--color-kind-recovered)',
  corrupt: 'var(--color-kind-corrupt)',
  unknown: 'var(--color-kind-unknown)',
}

const UNKNOWN_FILL = 'var(--color-kind-unknown)'

const ROW_HEIGHT = 34
const ROW_GAP = 10
const LEFT_LABEL_WIDTH = 64
const CHART_WIDTH = 760
const AXIS_HEIGHT = 24

/** A real SVG rendering of every channel's segments on a shared time
 * axis, colored by kind -- not a placeholder chart. Assumes `segments`
 * is non-empty; the caller renders an EmptyState instead when it isn't. */
export function TimelineChart({ segments }: { segments: Segment[] }) {
  const channels = [...new Set(segments.map((s) => s.channel))].sort((a, b) => a - b)

  const times = segments.flatMap((s) => [new Date(s.start).getTime(), new Date(s.end).getTime()])
  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)
  const span = Math.max(maxTime - minTime, 1)

  const totalWidth = LEFT_LABEL_WIDTH + CHART_WIDTH
  const totalHeight = channels.length * (ROW_HEIGHT + ROW_GAP) + AXIS_HEIGHT

  const xFor = (epochMs: number) => LEFT_LABEL_WIDTH + ((epochMs - minTime) / span) * CHART_WIDTH

  return (
    <svg
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      className="w-full"
      role="img"
      aria-label="Multi-channel timeline"
    >
      {channels.map((channel, rowIndex) => {
        const y = rowIndex * (ROW_HEIGHT + ROW_GAP)
        const rowSegments = segments.filter((s) => s.channel === channel)
        return (
          <g key={channel}>
            <text x={0} y={y + ROW_HEIGHT / 2} dominantBaseline="middle" className="fill-text-secondary text-[11px]">
              Ch. {channel}
            </text>
            <rect
              x={LEFT_LABEL_WIDTH}
              y={y}
              width={CHART_WIDTH}
              height={ROW_HEIGHT}
              rx={4}
              className="fill-surface-2"
            />
            {rowSegments.map((segment) => {
              const x1 = xFor(new Date(segment.start).getTime())
              const x2 = xFor(new Date(segment.end).getTime())
              const width = Math.max(x2 - x1, 2)
              return (
                <rect
                  key={`${segment.channel}-${segment.start}-${segment.end}`}
                  x={x1}
                  y={y}
                  width={width}
                  height={ROW_HEIGHT}
                  rx={3}
                  fill={KIND_FILL[segment.kind] ?? UNKNOWN_FILL}
                >
                  <title>
                    {`Channel ${segment.channel} · ${segment.kind} · ${segment.start} to ${segment.end}`}
                  </title>
                </rect>
              )
            })}
          </g>
        )
      })}
      <text x={LEFT_LABEL_WIDTH} y={totalHeight - 4} className="fill-text-muted text-[10px]">
        {new Date(minTime).toLocaleString()}
      </text>
      <text x={totalWidth} y={totalHeight - 4} textAnchor="end" className="fill-text-muted text-[10px]">
        {new Date(maxTime).toLocaleString()}
      </text>
    </svg>
  )
}
