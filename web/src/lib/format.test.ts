import { describe, expect, it } from 'vitest'
import { formatBytes, formatDateTime, formatDuration } from './format'

describe('formatBytes', () => {
  it('renders sub-1024 byte counts as plain bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1023)).toBe('1023 B')
  })

  it('renders kilobytes with one decimal place', () => {
    expect(formatBytes(1536)).toBe('1.5 KB')
  })

  it('scales up through the unit ladder for large sizes', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB')
    expect(formatBytes(1024 ** 4)).toBe('1.0 TB')
  })

  it('does not overflow past the largest known unit', () => {
    expect(formatBytes(1024 ** 5)).toBe('1024.0 TB')
  })
})

describe('formatDateTime', () => {
  it('falls back to the raw string for unparseable input', () => {
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })

  it('formats a valid ISO timestamp without throwing', () => {
    const result = formatDateTime('2026-01-01T12:00:00Z')
    expect(result).not.toBe('2026-01-01T12:00:00Z')
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('formatDuration', () => {
  it('renders a sub-minute duration as seconds only', () => {
    expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T00:00:45Z')).toBe('45s')
  })

  it('renders a multi-minute duration with minutes and seconds', () => {
    expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T00:05:30Z')).toBe('5m 30s')
  })

  it('renders a multi-hour duration with hours, minutes, and seconds', () => {
    expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T02:15:10Z')).toBe('2h 15m 10s')
  })

  it('returns an em dash when the end precedes the start', () => {
    expect(formatDuration('2026-01-01T02:00:00Z', '2026-01-01T01:00:00Z')).toBe('—')
  })

  it('returns an em dash for unparseable input', () => {
    expect(formatDuration('bad', '2026-01-01T00:00:00Z')).toBe('—')
  })
})
