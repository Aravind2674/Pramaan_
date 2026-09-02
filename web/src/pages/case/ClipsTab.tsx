import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { SEGMENT_KINDS } from '../../api/types'
import { KindBadge } from '../../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { PrimaryButton, SecondaryButton, SelectField, TextField } from '../../components/ui/form'
import { queryKeys, useClips, useEvidence } from '../../hooks/queries'
import { useCaseId } from '../../hooks/useCaseId'
import type { Clip } from '../../api/types'

function AddClipForm({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const evidenceQuery = useEvidence(caseId)

  const [evidenceItemId, setEvidenceItemId] = useState('')
  const [channel, setChannel] = useState('0')
  const [kind, setKind] = useState<string>(SEGMENT_KINDS[0])
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [note, setNote] = useState('')

  const addClip = useMutation({
    mutationFn: () =>
      api.addClip(caseId, {
        evidence_item_id: Number(evidenceItemId),
        channel: Number(channel),
        kind,
        start_time: startTime === '' ? null : startTime,
        end_time: endTime === '' ? null : endTime,
        note,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.clips(caseId) })
      await queryClient.invalidateQueries({ queryKey: queryKeys.timeline(caseId) })
      onDone()
    },
  })

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        addClip.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="clip-evidence-item" className="mb-1 block text-xs font-medium text-text-secondary">
            Evidence item<span className="text-danger"> *</span>
          </label>
          <select
            id="clip-evidence-item"
            required
            value={evidenceItemId}
            onChange={(e) => { setEvidenceItemId(e.target.value) }}
            className="w-full rounded-md border border-line bg-surface-2 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">
              {evidenceQuery.data?.length === 0 ? 'No evidence items yet' : 'Select an evidence item'}
            </option>
            {evidenceQuery.data?.map((item) => (
              <option key={item.id} value={item.id}>
                #{item.id}: {item.description}
              </option>
            ))}
          </select>
        </div>
        <TextField
          label="Channel"
          required
          type="number"
          min={0}
          value={channel}
          onChange={(e) => { setChannel(e.target.value) }}
        />
        <SelectField
          label="Kind"
          required
          options={SEGMENT_KINDS}
          value={kind}
          onChange={(e) => { setKind(e.target.value) }}
        />
        <TextField
          label="Note"
          value={note}
          onChange={(e) => { setNote(e.target.value) }}
        />
        <TextField
          label="Start time (optional)"
          type="datetime-local"
          value={startTime}
          onChange={(e) => { setStartTime(e.target.value) }}
        />
        <TextField
          label="End time (optional)"
          type="datetime-local"
          value={endTime}
          onChange={(e) => { setEndTime(e.target.value) }}
        />
      </div>

      {addClip.isError && <ErrorBanner error={addClip.error} />}

      <div className="flex justify-end gap-2">
        <SecondaryButton onClick={onDone}>Cancel</SecondaryButton>
        <PrimaryButton type="submit" disabled={addClip.isPending || evidenceItemId === ''}>
          {addClip.isPending ? 'Adding…' : 'Add clip'}
        </PrimaryButton>
      </div>
    </form>
  )
}

function TimeRangeEditor({ caseId, clip }: { caseId: string; clip: Clip }) {
  const queryClient = useQueryClient()
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')

  const setTimeRange = useMutation({
    mutationFn: () => api.setClipTimeRange(caseId, clip.id, { start_time: startTime, end_time: endTime }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.clips(caseId) })
      await queryClient.invalidateQueries({ queryKey: queryKeys.timeline(caseId) })
    },
  })

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <TextField
        label="Start time"
        type="datetime-local"
        value={startTime}
        onChange={(e) => { setStartTime(e.target.value) }}
      />
      <TextField
        label="End time"
        type="datetime-local"
        value={endTime}
        onChange={(e) => { setEndTime(e.target.value) }}
      />
      <SecondaryButton
        onClick={() => { setTimeRange.mutate() }}
        disabled={setTimeRange.isPending || startTime === '' || endTime === ''}
      >
        {setTimeRange.isPending ? 'Saving…' : 'Set time range'}
      </SecondaryButton>
      {setTimeRange.isError && <ErrorBanner error={setTimeRange.error} />}
    </div>
  )
}

export function ClipsTab() {
  const caseId = useCaseId()
  const clipsQuery = useClips(caseId)
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader
          title="Add clip"
          subtitle="Records a clip found via index walk, carving, or manual annotation."
          action={!showForm && <PrimaryButton onClick={() => { setShowForm(true) }}>Add clip</PrimaryButton>}
        />
        {showForm && (
          <CardBody>
            <AddClipForm caseId={caseId} onDone={() => { setShowForm(false) }} />
          </CardBody>
        )}
      </Card>

      {clipsQuery.isPending && <Spinner label="Loading clips…" />}
      {clipsQuery.isError && <ErrorBanner error={clipsQuery.error} />}
      {clipsQuery.isSuccess && clipsQuery.data.length === 0 && <EmptyState>No clips recorded yet.</EmptyState>}
      {clipsQuery.isSuccess && clipsQuery.data.length > 0 && (
        <div className="grid gap-3">
          {clipsQuery.data.map((clip) => (
            <Card key={clip.id}>
              <CardBody>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-text-primary">
                      Channel {clip.channel} · clip #{clip.id}
                    </p>
                    <p className="mt-1 text-xs text-text-secondary">
                      {clip.start_time ?? 'unknown'} → {clip.end_time ?? 'unknown'}
                      {clip.frame_count !== null && ` · ${clip.frame_count} frames`}
                    </p>
                    {clip.sha256 !== null && (
                      <p className="mt-1 font-mono-data text-xs text-text-muted">{clip.sha256}</p>
                    )}
                    {clip.note !== '' && <p className="mt-1 text-xs text-text-muted">{clip.note}</p>}
                  </div>
                  <KindBadge kind={clip.kind} />
                </div>
                {(clip.start_time === null || clip.end_time === null) && (
                  <TimeRangeEditor caseId={caseId} clip={clip} />
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
