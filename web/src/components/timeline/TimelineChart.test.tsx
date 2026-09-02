import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Segment } from '../../api/types'
import { TimelineChart } from './TimelineChart'

function segment(overrides: Partial<Segment>): Segment {
  return {
    channel: 0,
    start: '2026-01-01T00:00:00Z',
    end: '2026-01-01T01:00:00Z',
    kind: 'recorded',
    first_sequence: null,
    last_sequence: null,
    note: '',
    ...overrides,
  }
}

describe('TimelineChart', () => {
  it('renders one background track plus one colored rect per segment', () => {
    const segments = [
      segment({ channel: 0, kind: 'recorded' }),
      segment({ channel: 0, kind: 'recovered', start: '2026-01-01T01:00:00Z', end: '2026-01-01T02:00:00Z' }),
      segment({ channel: 1, kind: 'corrupt' }),
    ]
    const { container } = render(<TimelineChart segments={segments} />)

    // 2 channels -> 2 background tracks, plus one rect per segment.
    const rects = container.querySelectorAll('rect')
    expect(rects).toHaveLength(2 + segments.length)
  })

  it('labels every distinct channel', () => {
    const segments = [segment({ channel: 0 }), segment({ channel: 3 })]
    const { getByText } = render(<TimelineChart segments={segments} />)

    expect(getByText('Ch. 0')).toBeInTheDocument()
    expect(getByText('Ch. 3')).toBeInTheDocument()
  })

  it('colors a segment by its kind, falling back to the unknown color for an unrecognized kind', () => {
    const segments = [segment({ kind: 'not-a-real-kind' })]
    const { container } = render(<TimelineChart segments={segments} />)

    const coloredRect = [...container.querySelectorAll('rect')].find(
      (rect) => rect.getAttribute('fill') !== null,
    )
    expect(coloredRect?.getAttribute('fill')).toBe('var(--color-kind-unknown)')
  })

  it('gives every segment a nonzero-width tooltip describing it', () => {
    const segments = [segment({})]
    const { container } = render(<TimelineChart segments={segments} />)

    const title = container.querySelector('title')
    expect(title?.textContent).toContain('Channel 0')
    expect(title?.textContent).toContain('recorded')
  })
})
