import { StatusBadge } from '../../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { useIntegrity } from '../../hooks/queries'
import { useCaseId } from '../../hooks/useCaseId'

export function IntegrityTab() {
  const caseId = useCaseId()
  const integrityQuery = useIntegrity(caseId)

  return (
    <Card>
      <CardHeader
        title="Audit ledger integrity"
        subtitle="Every mutating action on this case is automatically recorded into a hash-chained ledger."
      />
      <CardBody>
        {integrityQuery.isPending && <Spinner label="Verifying ledger…" />}
        {integrityQuery.isError && <ErrorBanner error={integrityQuery.error} />}
        {integrityQuery.isSuccess && (
          <div className="grid gap-3">
            <div>
              {integrityQuery.data.valid ? (
                <StatusBadge tone="success">Chain valid -- no break detected</StatusBadge>
              ) : (
                <StatusBadge tone="danger">Chain broken</StatusBadge>
              )}
            </div>
            {!integrityQuery.data.valid && (
              <div className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
                <p>Break at entry index: {integrityQuery.data.break_at_index}</p>
                <p className="mt-1">Reason: {integrityQuery.data.reason}</p>
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
