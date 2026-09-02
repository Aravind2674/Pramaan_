import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { PrimaryButton, SecondaryButton, SelectField, TextField } from '../../components/ui/form'
import { DEVICE_TYPES } from '../../api/types'
import { queryKeys, useEvidence } from '../../hooks/queries'
import { useCaseId } from '../../hooks/useCaseId'
import { formatBytes, formatDateTime } from '../../lib/format'

function AddEvidenceForm({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [description, setDescription] = useState('')
  const [sourcePath, setSourcePath] = useState('')
  const [sha256, setSha256] = useState('')
  const [sizeBytes, setSizeBytes] = useState('')
  const [deviceType, setDeviceType] = useState('')
  const [makeModel, setMakeModel] = useState('')
  const [serialNumber, setSerialNumber] = useState('')

  const addEvidence = useMutation({
    mutationFn: () =>
      api.addEvidence(caseId, {
        description,
        source_path: sourcePath,
        sha256,
        size_bytes: Number(sizeBytes),
        device_type: deviceType === '' ? null : deviceType,
        make_model: makeModel === '' ? null : makeModel,
        serial_number: serialNumber === '' ? null : serialNumber,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.evidence(caseId) })
      onDone()
    },
  })

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        addEvidence.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Description"
          required
          value={description}
          onChange={(e) => { setDescription(e.target.value) }}
          placeholder="Dahua XVR hard disk image"
        />
        <TextField
          label="Source path"
          required
          value={sourcePath}
          onChange={(e) => { setSourcePath(e.target.value) }}
          placeholder="/evidence/disk1.img"
        />
        <TextField
          label="SHA-256"
          required
          value={sha256}
          onChange={(e) => { setSha256(e.target.value) }}
          placeholder="64 hex characters"
          className="font-mono-data"
        />
        <TextField
          label="Size (bytes)"
          required
          type="number"
          min={0}
          value={sizeBytes}
          onChange={(e) => { setSizeBytes(e.target.value) }}
        />
        <SelectField
          label="Device type"
          options={DEVICE_TYPES}
          placeholder="Not specified"
          value={deviceType}
          onChange={(e) => { setDeviceType(e.target.value) }}
        />
        <TextField
          label="Make and model"
          value={makeModel}
          onChange={(e) => { setMakeModel(e.target.value) }}
          placeholder="Dahua XVR5108HS"
        />
        <TextField
          label="Serial number"
          value={serialNumber}
          onChange={(e) => { setSerialNumber(e.target.value) }}
        />
      </div>

      {addEvidence.isError && <ErrorBanner error={addEvidence.error} />}

      <div className="flex justify-end gap-2">
        <SecondaryButton onClick={onDone}>Cancel</SecondaryButton>
        <PrimaryButton type="submit" disabled={addEvidence.isPending}>
          {addEvidence.isPending ? 'Adding…' : 'Add evidence item'}
        </PrimaryButton>
      </div>
    </form>
  )
}

export function EvidenceTab() {
  const caseId = useCaseId()
  const evidenceQuery = useEvidence(caseId)
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader
          title="Add evidence item"
          subtitle="Records an already-acquired source -- this does not perform acquisition itself."
          action={
            !showForm && <PrimaryButton onClick={() => { setShowForm(true) }}>Add evidence item</PrimaryButton>
          }
        />
        {showForm && (
          <CardBody>
            <AddEvidenceForm caseId={caseId} onDone={() => { setShowForm(false) }} />
          </CardBody>
        )}
      </Card>

      {evidenceQuery.isPending && <Spinner label="Loading evidence…" />}
      {evidenceQuery.isError && <ErrorBanner error={evidenceQuery.error} />}
      {evidenceQuery.isSuccess && evidenceQuery.data.length === 0 && (
        <EmptyState>No evidence items recorded yet.</EmptyState>
      )}
      {evidenceQuery.isSuccess && evidenceQuery.data.length > 0 && (
        <div className="grid gap-3">
          {evidenceQuery.data.map((item) => (
            <Card key={item.id}>
              <CardBody>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-text-primary">
                      #{item.id}: {item.description}
                    </p>
                    <p className="mt-1 text-xs text-text-secondary">
                      {[item.device_type, item.make_model].filter(Boolean).join(' / ') || 'Device not specified'}
                      {' · '}
                      {formatBytes(item.size_bytes)} · acquired {formatDateTime(item.acquired_at)}
                    </p>
                    <p className="mt-2 font-mono-data text-xs text-text-muted">{item.sha256}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
