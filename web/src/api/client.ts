import { ApiError } from './errors'
import type {
  ArtifactSpecPayload,
  CaseCreatePayload,
  CaseInfo,
  CaseReportGeneratePayload,
  CertificateGeneratePayload,
  ChainVerification,
  Clip,
  ClipCreatePayload,
  ClipTimeRangePayload,
  EvidenceItem,
  EvidenceItemCreatePayload,
  ExportBuildPayload,
  Finding,
  FindingCreatePayload,
  Timeline,
} from './types'

/**
 * Base URL for every request this client makes. `/api` is proxied to the
 * FastAPI service in development (see vite.config.ts); in production the
 * deployment is expected to serve or reverse-proxy the API under the same
 * prefix, or `VITE_API_BASE_URL` can point it elsewhere entirely.
 */
const BASE_URL = ((import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? '/api').replace(
  /\/$/,
  '',
)

/** FastAPI's own 422 body shape: a list of per-field validation errors,
 * not a plain string -- every other error path here returns a plain
 * `detail` string, so this is normalized into one at the boundary. */
interface FastApiValidationError {
  loc: (string | number)[]
  msg: string
}

function extractErrorDetail(body: unknown, fallback: string): string {
  if (body !== null && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => {
          const e = entry as Partial<FastApiValidationError>
          const field = Array.isArray(e.loc) ? e.loc.join('.') : 'value'
          return `${field}: ${e.msg ?? 'invalid'}`
        })
        .join('; ')
    }
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, extractErrorDetail(body, response.statusText))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** A downloaded file: the raw bytes plus the filename the server suggested
 * via Content-Disposition, so callers never have to guess or re-derive it. */
export interface DownloadedFile {
  blob: Blob
  filename: string
}

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (header === null) return fallback
  const match = /filename="([^"]+)"/.exec(header)
  return match?.[1] ?? fallback
}

async function requestFile(
  path: string,
  init: RequestInit,
  fallbackFilename: string,
): Promise<DownloadedFile> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, extractErrorDetail(body, response.statusText))
  }
  const blob = await response.blob()
  const filename = filenameFromContentDisposition(
    response.headers.get('Content-Disposition'),
    fallbackFilename,
  )
  return { blob, filename }
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  listCases: () => request<CaseInfo[]>('/cases'),
  getCase: (caseId: string) => request<CaseInfo>(`/cases/${encodeURIComponent(caseId)}`),
  createCase: (payload: CaseCreatePayload) => request<CaseInfo>('/cases', json(payload)),

  listEvidence: (caseId: string) =>
    request<EvidenceItem[]>(`/cases/${encodeURIComponent(caseId)}/evidence`),
  addEvidence: (caseId: string, payload: EvidenceItemCreatePayload) =>
    request<EvidenceItem>(`/cases/${encodeURIComponent(caseId)}/evidence`, json(payload)),

  listClips: (caseId: string) => request<Clip[]>(`/cases/${encodeURIComponent(caseId)}/clips`),
  addClip: (caseId: string, payload: ClipCreatePayload) =>
    request<Clip>(`/cases/${encodeURIComponent(caseId)}/clips`, json(payload)),
  setClipTimeRange: (caseId: string, clipId: number, payload: ClipTimeRangePayload) =>
    request<Clip>(`/cases/${encodeURIComponent(caseId)}/clips/${clipId}/time-range`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  listFindings: (caseId: string) =>
    request<Finding[]>(`/cases/${encodeURIComponent(caseId)}/findings`),
  addFinding: (caseId: string, payload: FindingCreatePayload) =>
    request<Finding>(`/cases/${encodeURIComponent(caseId)}/findings`, json(payload)),

  getTimeline: (caseId: string) =>
    request<Timeline>(`/cases/${encodeURIComponent(caseId)}/timeline`),
  getIntegrity: (caseId: string) =>
    request<ChainVerification>(`/cases/${encodeURIComponent(caseId)}/integrity`),

  generateCertificate: (caseId: string, payload: CertificateGeneratePayload) =>
    requestFile(
      `/cases/${encodeURIComponent(caseId)}/reports/certificate`,
      json(payload),
      `${caseId}_certificate.pdf`,
    ),
  generateCaseReport: (caseId: string, payload: CaseReportGeneratePayload) =>
    requestFile(
      `/cases/${encodeURIComponent(caseId)}/reports/case-report`,
      json(payload),
      `${caseId}_report.pdf`,
    ),
  exportCase: (
    caseId: string,
    artifacts: ArtifactSpecPayload[],
    includeLedger: boolean,
  ) =>
    requestFile(
      `/cases/${encodeURIComponent(caseId)}/export`,
      json({ artifacts, include_ledger: includeLedger } satisfies ExportBuildPayload),
      `${caseId}.sef.zip`,
    ),
}
