import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { CaseDetailPage } from './pages/CaseDetailPage'
import { CaseListPage } from './pages/CaseListPage'
import { ClipsTab } from './pages/case/ClipsTab'
import { EvidenceTab } from './pages/case/EvidenceTab'
import { ExportTab } from './pages/case/ExportTab'
import { FindingsTab } from './pages/case/FindingsTab'
import { IntegrityTab } from './pages/case/IntegrityTab'
import { OverviewTab } from './pages/case/OverviewTab'
import { ReportsTab } from './pages/case/ReportsTab'
import { TimelineTab } from './pages/case/TimelineTab'
import { NewCasePage } from './pages/NewCasePage'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<CaseListPage />} />
        <Route path="/cases/new" element={<NewCasePage />} />
        <Route path="/cases/:caseId" element={<CaseDetailPage />}>
          <Route index element={<OverviewTab />} />
          <Route path="evidence" element={<EvidenceTab />} />
          <Route path="clips" element={<ClipsTab />} />
          <Route path="timeline" element={<TimelineTab />} />
          <Route path="findings" element={<FindingsTab />} />
          <Route path="integrity" element={<IntegrityTab />} />
          <Route path="reports" element={<ReportsTab />} />
          <Route path="export" element={<ExportTab />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
