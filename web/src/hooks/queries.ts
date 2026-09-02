import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

/** Every query key used by this app, centralized so a mutation's
 * `invalidateQueries` call and a query's own key can never drift apart
 * by one component using a hand-typed array and another a helper. */
export const queryKeys = {
  cases: ['cases'] as const,
  case: (caseId: string) => ['cases', caseId] as const,
  evidence: (caseId: string) => ['cases', caseId, 'evidence'] as const,
  clips: (caseId: string) => ['cases', caseId, 'clips'] as const,
  findings: (caseId: string) => ['cases', caseId, 'findings'] as const,
  timeline: (caseId: string) => ['cases', caseId, 'timeline'] as const,
  integrity: (caseId: string) => ['cases', caseId, 'integrity'] as const,
}

export function useCases() {
  return useQuery({ queryKey: queryKeys.cases, queryFn: api.listCases })
}

export function useCase(caseId: string) {
  return useQuery({ queryKey: queryKeys.case(caseId), queryFn: () => api.getCase(caseId) })
}

export function useEvidence(caseId: string) {
  return useQuery({ queryKey: queryKeys.evidence(caseId), queryFn: () => api.listEvidence(caseId) })
}

export function useClips(caseId: string) {
  return useQuery({ queryKey: queryKeys.clips(caseId), queryFn: () => api.listClips(caseId) })
}

export function useFindings(caseId: string) {
  return useQuery({ queryKey: queryKeys.findings(caseId), queryFn: () => api.listFindings(caseId) })
}

export function useTimeline(caseId: string) {
  return useQuery({ queryKey: queryKeys.timeline(caseId), queryFn: () => api.getTimeline(caseId) })
}

export function useIntegrity(caseId: string) {
  return useQuery({ queryKey: queryKeys.integrity(caseId), queryFn: () => api.getIntegrity(caseId) })
}
