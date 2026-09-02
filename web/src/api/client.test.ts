import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'
import { ApiError } from './errors'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api.listCases', () => {
  it('requests the /cases endpoint and returns the parsed body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([{ case_id: 'c1' }]))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.listCases()

    expect(result).toEqual([{ case_id: 'c1' }])
    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url).toBe('/api/cases')
  })

  it('throws an ApiError carrying the server-supplied detail on failure', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: 'a case with ID already exists' }, { status: 409 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.listCases()).rejects.toMatchObject({
      status: 409,
      detail: 'a case with ID already exists',
    })
  })

  it('normalizes a FastAPI 422 validation-error list into one readable string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        { detail: [{ loc: ['body', 'case_id'], msg: 'field required' }] },
        { status: 422 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    try {
      await api.listCases()
      expect.unreachable('expected listCases to throw')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).detail).toBe('body.case_id: field required')
    }
  })

  it('falls back to the response status text when the body has no usable detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('not json', { status: 500, statusText: 'Internal Server Error' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.listCases()).rejects.toMatchObject({ detail: 'Internal Server Error' })
  })
})

describe('api.createCase', () => {
  it('POSTs the payload as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ case_id: 'c1' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.createCase({
      case_id: 'c1',
      title: 'T',
      investigating_agency: 'A',
      examiner_name: 'E',
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      case_id: 'c1',
      title: 'T',
      investigating_agency: 'A',
      examiner_name: 'E',
    })
  })
})

describe('api.generateCertificate', () => {
  it('extracts the filename from the Content-Disposition header', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': 'attachment; filename="c1_certificate.pdf"',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.generateCertificate('c1', {
      part_a: {
        custodian_name: 'x',
        custodian_address: 'x',
        device: { device_type: 'DVR', make_and_model: 'x' },
        lawful_control_declared: true,
        functioning_properly_declared: true,
        hash: { algorithm: 'SHA256', value: 'a'.repeat(64) },
        place: 'x',
        date: '2026-01-01',
        time_ist: '12:00',
      },
      part_b: {
        expert_name: 'x',
        expert_designation: 'x',
        device: { device_type: 'DVR', make_and_model: 'x' },
        hash: { algorithm: 'SHA256', value: 'a'.repeat(64) },
        technical_statement: 'x',
        place: 'x',
        date: '2026-01-01',
        time_ist: '12:00',
      },
    })

    expect(result.filename).toBe('c1_certificate.pdf')
    expect(result.blob.type).toBe('application/pdf')
  })

  it('falls back to a generated filename when the header is missing', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    const fetchMock = vi.fn().mockResolvedValue(new Response(blob, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.generateCaseReport('c1', {})

    expect(result.filename).toBe('c1_report.pdf')
  })
})
