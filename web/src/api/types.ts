/**
 * TypeScript mirrors of pramaan.api.schemas.
 *
 * These are hand-written, not generated, and deliberately shaped to
 * match the Pydantic models field-for-field -- there is exactly one
 * source of truth for what the API returns (pramaan/api/schemas.py),
 * and this file's job is to stay in sync with it, not to reinterpret it.
 */

export const SEGMENT_KINDS = ['recorded', 'recovered', 'corrupt', 'unknown'] as const
export type SegmentKindValue = (typeof SEGMENT_KINDS)[number]

export interface CaseInfo {
  case_id: string
  title: string
  investigating_agency: string
  examiner_name: string
  created_at: string
}

export interface CaseCreatePayload {
  case_id: string
  title: string
  investigating_agency: string
  examiner_name: string
}

export interface WriteBlockAttestation {
  path: string
  write_open_refused: boolean
  detail: string
}

export interface EvidenceItem {
  id: number
  description: string
  device_type: string | null
  make_model: string | null
  serial_number: string | null
  source_path: string
  sha256: string
  size_bytes: number
  acquired_at: string
  write_block_attestation: WriteBlockAttestation | null
}

export interface EvidenceItemCreatePayload {
  description: string
  source_path: string
  sha256: string
  size_bytes: number
  device_type?: string | null
  make_model?: string | null
  serial_number?: string | null
  acquired_at?: string | null
  actor?: string | null
}

export interface Clip {
  id: number
  evidence_item_id: number
  channel: number
  kind: string
  start_offset: number | null
  end_offset: number | null
  start_time: string | null
  end_time: string | null
  first_sequence: number | null
  last_sequence: number | null
  frame_count: number | null
  sha256: string | null
  format_id: string | null
  note: string
}

export interface ClipCreatePayload {
  evidence_item_id: number
  channel: number
  kind: string
  start_offset?: number | null
  end_offset?: number | null
  start_time?: string | null
  end_time?: string | null
  first_sequence?: number | null
  last_sequence?: number | null
  frame_count?: number | null
  sha256?: string | null
  format_id?: string | null
  note?: string
  actor?: string | null
}

export interface ClipTimeRangePayload {
  start_time: string
  end_time: string
  actor?: string | null
}

export interface Finding {
  id: number
  created_at: string
  author: string
  clip_id: number | null
  category: string
  description: string
}

export interface FindingCreatePayload {
  author: string
  category: string
  description: string
  clip_id?: number | null
  created_at?: string | null
}

export interface Segment {
  channel: number
  start: string
  end: string
  kind: string
  first_sequence: number | null
  last_sequence: number | null
  note: string
}

export interface Timeline {
  segments: Segment[]
}

export interface ChainVerification {
  valid: boolean
  break_at_index: number | null
  reason: string | null
}

export interface DeviceDetailsPayload {
  device_type: string
  make_and_model: string
  serial_number?: string | null
  identifier?: string | null
  other_device_type?: string | null
}

export interface HashDeclarationPayload {
  algorithm: string
  value: string
  other_algorithm_name?: string | null
}

export interface CertificatePartAPayload {
  custodian_name: string
  custodian_address: string
  device: DeviceDetailsPayload
  lawful_control_declared: boolean
  functioning_properly_declared: boolean
  hash: HashDeclarationPayload
  place: string
  date: string
  time_ist: string
}

export interface CertificatePartBPayload {
  expert_name: string
  expert_designation: string
  device: DeviceDetailsPayload
  hash: HashDeclarationPayload
  technical_statement: string
  place: string
  date: string
  time_ist: string
}

export interface CertificateGeneratePayload {
  part_a: CertificatePartAPayload
  part_b: CertificatePartBPayload
}

export interface GapAnalysisWindowPayload {
  start: string
  end: string
}

export interface CaseReportGeneratePayload {
  gap_analysis_window?: GapAnalysisWindowPayload | null
}

export interface ArtifactSpecPayload {
  artifact_id: string
  source_path: string
  description?: string
}

export interface ExportBuildPayload {
  artifacts: ArtifactSpecPayload[]
  include_ledger?: boolean
}

export const DEVICE_TYPES = [
  'Computer',
  'DVR',
  'NVR',
  'Mobile Phone',
  'Flash Drive',
  'Hard Disk',
  'Other',
] as const

export const HASH_ALGORITHMS = ['SHA1', 'SHA256', 'MD5', 'Other'] as const
