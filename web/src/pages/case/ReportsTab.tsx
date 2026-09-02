import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type {
  CertificatePartAPayload,
  CertificatePartBPayload,
  DeviceDetailsPayload,
  HashDeclarationPayload,
} from '../../api/types'
import { DeviceFields, HashFields } from '../../components/forms/DeviceHashFields'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorBanner } from '../../components/ui/Feedback'
import { CheckboxField, PrimaryButton, TextAreaField, TextField } from '../../components/ui/form'
import { useCaseId } from '../../hooks/useCaseId'
import { saveDownloadedFile } from '../../lib/download'

const emptyDevice: DeviceDetailsPayload = { device_type: 'DVR', make_and_model: '' }
const emptyHash: HashDeclarationPayload = { algorithm: 'SHA256', value: '' }

function CertificateForm({ caseId }: { caseId: string }) {
  const [partA, setPartA] = useState<CertificatePartAPayload>({
    custodian_name: '',
    custodian_address: '',
    device: emptyDevice,
    lawful_control_declared: false,
    functioning_properly_declared: false,
    hash: emptyHash,
    place: '',
    date: '',
    time_ist: '',
  })
  const [partB, setPartB] = useState<CertificatePartBPayload>({
    expert_name: '',
    expert_designation: '',
    device: emptyDevice,
    hash: emptyHash,
    technical_statement: '',
    place: '',
    date: '',
    time_ist: '',
  })

  const generate = useMutation({
    mutationFn: () => api.generateCertificate(caseId, { part_a: partA, part_b: partB }),
    onSuccess: (file) => { saveDownloadedFile(file) },
  })

  return (
    <Card>
      <CardHeader
        title="Section 63(4) certificate"
        subtitle="The statutory admissibility certificate -- Part A (device custodian) and Part B (technical expert)."
      />
      <CardBody>
        <form
          className="grid gap-6"
          onSubmit={(event) => {
            event.preventDefault()
            generate.mutate()
          }}
        >
          <fieldset className="grid gap-4 rounded-lg border border-line p-4">
            <legend className="px-1 text-sm font-semibold text-text-primary">Part A -- device custodian</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Custodian name"
                required
                value={partA.custodian_name}
                onChange={(e) => { setPartA({ ...partA, custodian_name: e.target.value }) }}
              />
              <TextField
                label="Custodian address"
                required
                value={partA.custodian_address}
                onChange={(e) => { setPartA({ ...partA, custodian_address: e.target.value }) }}
              />
            </div>
            <DeviceFields value={partA.device} onChange={(device) => { setPartA({ ...partA, device }) }} />
            <HashFields value={partA.hash} onChange={(hash) => { setPartA({ ...partA, hash }) }} />
            <div className="grid gap-2">
              <CheckboxField
                id="cert-lawful-control"
                label="I declare the device was under my lawful control throughout the material period."
                checked={partA.lawful_control_declared}
                onChange={(checked) => { setPartA({ ...partA, lawful_control_declared: checked }) }}
              />
              <CheckboxField
                id="cert-functioning"
                label="I declare the device was operating properly throughout the material period."
                checked={partA.functioning_properly_declared}
                onChange={(checked) => { setPartA({ ...partA, functioning_properly_declared: checked }) }}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField
                label="Place"
                required
                value={partA.place}
                onChange={(e) => { setPartA({ ...partA, place: e.target.value }) }}
              />
              <TextField
                label="Date"
                type="date"
                required
                value={partA.date}
                onChange={(e) => { setPartA({ ...partA, date: e.target.value }) }}
              />
              <TextField
                label="Time (IST)"
                type="time"
                required
                value={partA.time_ist}
                onChange={(e) => { setPartA({ ...partA, time_ist: e.target.value }) }}
              />
            </div>
          </fieldset>

          <fieldset className="grid gap-4 rounded-lg border border-line p-4">
            <legend className="px-1 text-sm font-semibold text-text-primary">Part B -- technical expert</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Expert name"
                required
                value={partB.expert_name}
                onChange={(e) => { setPartB({ ...partB, expert_name: e.target.value }) }}
              />
              <TextField
                label="Expert designation"
                required
                value={partB.expert_designation}
                onChange={(e) => { setPartB({ ...partB, expert_designation: e.target.value }) }}
              />
            </div>
            <DeviceFields value={partB.device} onChange={(device) => { setPartB({ ...partB, device }) }} />
            <HashFields value={partB.hash} onChange={(hash) => { setPartB({ ...partB, hash }) }} />
            <TextAreaField
              label="Technical statement"
              required
              value={partB.technical_statement}
              onChange={(e) => { setPartB({ ...partB, technical_statement: e.target.value }) }}
              placeholder="The device was imaged read-only via a hardware write-blocker…"
            />
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField
                label="Place"
                required
                value={partB.place}
                onChange={(e) => { setPartB({ ...partB, place: e.target.value }) }}
              />
              <TextField
                label="Date"
                type="date"
                required
                value={partB.date}
                onChange={(e) => { setPartB({ ...partB, date: e.target.value }) }}
              />
              <TextField
                label="Time (IST)"
                type="time"
                required
                value={partB.time_ist}
                onChange={(e) => { setPartB({ ...partB, time_ist: e.target.value }) }}
              />
            </div>
          </fieldset>

          {generate.isError && <ErrorBanner error={generate.error} />}

          <div className="flex justify-end">
            <PrimaryButton type="submit" disabled={generate.isPending}>
              {generate.isPending ? 'Generating…' : 'Generate certificate PDF'}
            </PrimaryButton>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

function CaseReportForm({ caseId }: { caseId: string }) {
  const [includeGapAnalysis, setIncludeGapAnalysis] = useState(false)
  const [windowStart, setWindowStart] = useState('')
  const [windowEnd, setWindowEnd] = useState('')

  const generate = useMutation({
    mutationFn: () =>
      api.generateCaseReport(caseId, {
        gap_analysis_window:
          includeGapAnalysis && windowStart !== '' && windowEnd !== ''
            ? { start: windowStart, end: windowEnd }
            : null,
      }),
    onSuccess: (file) => { saveDownloadedFile(file) },
  })

  return (
    <Card>
      <CardHeader
        title="Narrative case report"
        subtitle="Case summary, evidence, recovery coverage, the clip exhibit list, findings, and ledger integrity."
      />
      <CardBody>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            generate.mutate()
          }}
        >
          <CheckboxField
            id="report-gap-analysis"
            label="Include timeline anomaly analysis"
            checked={includeGapAnalysis}
            onChange={setIncludeGapAnalysis}
          />
          {includeGapAnalysis && (
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Expected coverage start"
                type="datetime-local"
                required
                value={windowStart}
                onChange={(e) => { setWindowStart(e.target.value) }}
              />
              <TextField
                label="Expected coverage end"
                type="datetime-local"
                required
                value={windowEnd}
                onChange={(e) => { setWindowEnd(e.target.value) }}
              />
            </div>
          )}

          {generate.isError && <ErrorBanner error={generate.error} />}

          <div className="flex justify-end">
            <PrimaryButton type="submit" disabled={generate.isPending}>
              {generate.isPending ? 'Generating…' : 'Generate case report PDF'}
            </PrimaryButton>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

export function ReportsTab() {
  const caseId = useCaseId()
  return (
    <div className="grid gap-6">
      <CertificateForm caseId={caseId} />
      <CaseReportForm caseId={caseId} />
    </div>
  )
}
