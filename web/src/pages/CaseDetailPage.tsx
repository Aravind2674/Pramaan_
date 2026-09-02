import { NavLink, Outlet, useParams } from 'react-router-dom'
import { ErrorBanner, Spinner } from '../components/ui/Feedback'
import { useCase } from '../hooks/queries'

const TABS = [
  { to: '.', label: 'Overview', end: true },
  { to: 'evidence', label: 'Evidence' },
  { to: 'clips', label: 'Clips' },
  { to: 'timeline', label: 'Timeline' },
  { to: 'findings', label: 'Findings' },
  { to: 'integrity', label: 'Integrity' },
  { to: 'reports', label: 'Reports' },
  { to: 'export', label: 'Export' },
]

const TAB_BASE = 'border-b-2 px-1 pb-3 text-sm font-medium transition'
const TAB_ACTIVE = 'border-accent text-accent'
const TAB_INACTIVE = 'border-transparent text-text-secondary hover:text-text-primary'

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const caseQuery = useCase(caseId ?? '')

  if (caseId === undefined) return <ErrorBanner error={new Error('No case ID in URL.')} />

  return (
    <div>
      {caseQuery.isPending && <Spinner label="Loading case…" />}
      {caseQuery.isError && <ErrorBanner error={caseQuery.error} />}

      {caseQuery.isSuccess && (
        <>
          <div className="mb-2">
            <p className="font-mono-data text-xs text-text-muted">{caseQuery.data.case_id}</p>
            <h1 className="text-xl font-semibold text-text-primary">{caseQuery.data.title}</h1>
            <p className="mt-1 text-sm text-text-secondary">
              {caseQuery.data.investigating_agency} · {caseQuery.data.examiner_name}
            </p>
          </div>

          <nav className="mt-6 flex gap-6 border-b border-line">
            {TABS.map((tab) => (
              <NavLink
                key={tab.label}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) => `${TAB_BASE} ${isActive ? TAB_ACTIVE : TAB_INACTIVE}`}
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>

          <div className="py-6">
            <Outlet context={{ caseId }} />
          </div>
        </>
      )}
    </div>
  )
}
