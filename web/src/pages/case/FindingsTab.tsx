import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { PrimaryButton, SecondaryButton, TextAreaField, TextField } from '../../components/ui/form'
import { queryKeys, useClips, useFindings } from '../../hooks/queries'
import { useCaseId } from '../../hooks/useCaseId'
import { formatDateTime } from '../../lib/format'

function AddFindingForm({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const clipsQuery = useClips(caseId)

  const [author, setAuthor] = useState('')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [clipId, setClipId] = useState('')

  const addFinding = useMutation({
    mutationFn: () =>
      api.addFinding(caseId, {
        author,
        category,
        description,
        clip_id: clipId === '' ? null : Number(clipId),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.findings(caseId) })
      onDone()
    },
  })

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        addFinding.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label="Author" required value={author} onChange={(e) => { setAuthor(e.target.value) }} />
        <TextField
          label="Category"
          required
          value={category}
          onChange={(e) => { setCategory(e.target.value) }}
          placeholder="tamper_indicator, note, …"
        />
        <div>
          <label htmlFor="finding-clip" className="mb-1 block text-xs font-medium text-text-secondary">
            Associated clip (optional)
          </label>
          <select
            id="finding-clip"
            value={clipId}
            onChange={(e) => { setClipId(e.target.value) }}
            className="w-full rounded-md border border-line bg-surface-2 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">No associated clip</option>
            {clipsQuery.data?.map((clip) => (
              <option key={clip.id} value={clip.id}>
                Channel {clip.channel} · clip #{clip.id}
              </option>
            ))}
          </select>
        </div>
      </div>
      <TextAreaField
        label="Description"
        required
        value={description}
        onChange={(e) => { setDescription(e.target.value) }}
      />

      {addFinding.isError && <ErrorBanner error={addFinding.error} />}

      <div className="flex justify-end gap-2">
        <SecondaryButton onClick={onDone}>Cancel</SecondaryButton>
        <PrimaryButton type="submit" disabled={addFinding.isPending}>
          {addFinding.isPending ? 'Adding…' : 'Add finding'}
        </PrimaryButton>
      </div>
    </form>
  )
}

export function FindingsTab() {
  const caseId = useCaseId()
  const findingsQuery = useFindings(caseId)
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader
          title="Add finding"
          subtitle="An examiner's own recorded observation -- never generated automatically."
          action={!showForm && <PrimaryButton onClick={() => { setShowForm(true) }}>Add finding</PrimaryButton>}
        />
        {showForm && (
          <CardBody>
            <AddFindingForm caseId={caseId} onDone={() => { setShowForm(false) }} />
          </CardBody>
        )}
      </Card>

      {findingsQuery.isPending && <Spinner label="Loading findings…" />}
      {findingsQuery.isError && <ErrorBanner error={findingsQuery.error} />}
      {findingsQuery.isSuccess && findingsQuery.data.length === 0 && (
        <EmptyState>No findings recorded yet.</EmptyState>
      )}
      {findingsQuery.isSuccess && findingsQuery.data.length > 0 && (
        <div className="grid gap-3">
          {findingsQuery.data.map((finding) => (
            <Card key={finding.id}>
              <CardBody>
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent-strong">
                    {finding.category}
                  </span>
                  <span className="text-xs text-text-muted">{formatDateTime(finding.created_at)}</span>
                </div>
                <p className="mt-2 text-sm text-text-primary">{finding.description}</p>
                <p className="mt-2 text-xs text-text-muted">
                  {finding.author}
                  {finding.clip_id !== null && ` · clip #${finding.clip_id}`}
                </p>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
