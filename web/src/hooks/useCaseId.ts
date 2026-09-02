import { useOutletContext } from 'react-router-dom'

interface CaseOutletContext {
  caseId: string
}

/** The case ID for the currently active tab, supplied by CaseDetailPage's
 * <Outlet context={{ caseId }} /> -- every tab route lives under a case
 * and needs this, so it is typed once here rather than re-derived from
 * useParams (and re-validated for undefined) in every tab component. */
export function useCaseId(): string {
  return useOutletContext<CaseOutletContext>().caseId
}
