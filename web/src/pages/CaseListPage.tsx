import { Link } from 'react-router-dom'
import { Card, CardBody } from '../components/ui/Card'
import { EmptyState, ErrorBanner, Spinner } from '../components/ui/Feedback'
import { PrimaryButton } from '../components/ui/form'
import { useCases } from '../hooks/queries'
import { formatDateTime } from '../lib/format'

export function CaseListPage() {
  const casesQuery = useCases()

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Cases</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Every investigation in this workspace.
          </p>
        </div>
        <Link to="/cases/new">
          <PrimaryButton>New case</PrimaryButton>
        </Link>
      </div>

      {casesQuery.isPending && <Spinner label="Loading cases…" />}
      {casesQuery.isError && <ErrorBanner error={casesQuery.error} />}
      {casesQuery.isSuccess && casesQuery.data.length === 0 && (
        <EmptyState>
          No cases yet. <Link to="/cases/new" className="text-accent hover:underline">Create the first one.</Link>
        </EmptyState>
      )}
      {casesQuery.isSuccess && casesQuery.data.length > 0 && (
        <div className="grid gap-3">
          {casesQuery.data.map((c) => (
            <Link key={c.case_id} to={`/cases/${encodeURIComponent(c.case_id)}`}>
              <Card className="transition hover:border-line-strong">
                <CardBody className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-text-primary">{c.title}</p>
                    <p className="mt-0.5 text-xs text-text-muted">
                      <span className="font-mono-data">{c.case_id}</span> · {c.investigating_agency} ·{' '}
                      {c.examiner_name}
                    </p>
                  </div>
                  <p className="text-xs text-text-muted">{formatDateTime(c.created_at)}</p>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
