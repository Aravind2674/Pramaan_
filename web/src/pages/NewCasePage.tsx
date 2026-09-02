import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { ErrorBanner } from '../components/ui/Feedback'
import { PrimaryButton, SecondaryButton, TextField } from '../components/ui/form'
import { queryKeys } from '../hooks/queries'

export function NewCasePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [caseId, setCaseId] = useState('')
  const [title, setTitle] = useState('')
  const [investigatingAgency, setInvestigatingAgency] = useState('')
  const [examinerName, setExaminerName] = useState('')

  const createCase = useMutation({
    mutationFn: () =>
      api.createCase({
        case_id: caseId,
        title,
        investigating_agency: investigatingAgency,
        examiner_name: examinerName,
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.cases })
      navigate(`/cases/${encodeURIComponent(created.case_id)}`)
    },
  })

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">New case</h1>
      <Card>
        <CardHeader
          title="Case details"
          subtitle="The case ID becomes this case's permanent identifier -- it cannot be changed later."
        />
        <CardBody>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              createCase.mutate()
            }}
          >
            <TextField
              label="Case ID"
              required
              value={caseId}
              onChange={(e) => {
                setCaseId(e.target.value)
              }}
              placeholder="SIH26150-001"
              hint="Letters, digits, '_', '-', '.' only -- no spaces or slashes."
            />
            <TextField
              label="Title"
              required
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
              }}
              placeholder="Warehouse burglary — CCTV recovery"
            />
            <TextField
              label="Investigating agency"
              required
              value={investigatingAgency}
              onChange={(e) => {
                setInvestigatingAgency(e.target.value)
              }}
              placeholder="Cyber Cell, City Police"
            />
            <TextField
              label="Examiner name"
              required
              value={examinerName}
              onChange={(e) => {
                setExaminerName(e.target.value)
              }}
              placeholder="Dr. A. Examiner"
            />

            {createCase.isError && <ErrorBanner error={createCase.error} />}

            <div className="flex justify-end gap-2 pt-2">
              <SecondaryButton
                onClick={() => {
                  navigate('/')
                }}
              >
                Cancel
              </SecondaryButton>
              <PrimaryButton type="submit" disabled={createCase.isPending}>
                {createCase.isPending ? 'Creating…' : 'Create case'}
              </PrimaryButton>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
