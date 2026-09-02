import { Link } from 'react-router-dom'
import { Card, CardBody } from '../../components/ui/Card'
import { ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { StatusBadge } from '../../components/ui/Badge'
import { useCaseId } from '../../hooks/useCaseId'
import { useClips, useEvidence, useFindings, useIntegrity } from '../../hooks/queries'

function StatCard({ label, value, to }: { label: string; value: string; to: string }) {
  return (
    <Link to={to}>
      <Card className="transition hover:border-line-strong">
        <CardBody>
          <p className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-text-primary">{value}</p>
        </CardBody>
      </Card>
    </Link>
  )
}

export function OverviewTab() {
  const caseId = useCaseId()
  const evidenceQuery = useEvidence(caseId)
  const clipsQuery = useClips(caseId)
  const findingsQuery = useFindings(caseId)
  const integrityQuery = useIntegrity(caseId)

  const isPending =
    evidenceQuery.isPending || clipsQuery.isPending || findingsQuery.isPending || integrityQuery.isPending
  const firstError =
    evidenceQuery.error ?? clipsQuery.error ?? findingsQuery.error ?? integrityQuery.error

  if (isPending) return <Spinner label="Loading case overview…" />
  if (firstError) return <ErrorBanner error={firstError} />

  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Evidence items" value={String(evidenceQuery.data?.length ?? 0)} to="evidence" />
        <StatCard label="Clips" value={String(clipsQuery.data?.length ?? 0)} to="clips" />
        <StatCard label="Findings" value={String(findingsQuery.data?.length ?? 0)} to="findings" />
        <Link to="integrity">
          <Card className="transition hover:border-line-strong">
            <CardBody>
              <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Ledger integrity</p>
              <div className="mt-2">
                {integrityQuery.data?.valid === true ? (
                  <StatusBadge tone="success">Valid</StatusBadge>
                ) : (
                  <StatusBadge tone="danger">Broken</StatusBadge>
                )}
              </div>
            </CardBody>
          </Card>
        </Link>
      </div>

      <Card>
        <CardBody>
          <p className="text-sm text-text-secondary">
            Use the tabs above to record evidence intake, recovered clips, and examiner findings, review
            the composed timeline, verify the audit ledger, and generate the Section 63(4) certificate,
            the narrative case report, or a SEF export bundle.
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
