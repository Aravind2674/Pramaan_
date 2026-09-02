import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { ArtifactSpecPayload } from '../../api/types'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorBanner } from '../../components/ui/Feedback'
import { CheckboxField, PrimaryButton, SecondaryButton, TextField } from '../../components/ui/form'
import { useCaseId } from '../../hooks/useCaseId'
import { saveDownloadedFile } from '../../lib/download'

const emptyArtifact: ArtifactSpecPayload = { artifact_id: '', source_path: '', description: '' }

export function ExportTab() {
  const caseId = useCaseId()
  const [artifacts, setArtifacts] = useState<ArtifactSpecPayload[]>([])
  const [includeLedger, setIncludeLedger] = useState(true)

  const exportCase = useMutation({
    mutationFn: () => api.exportCase(caseId, artifacts, includeLedger),
    onSuccess: (file) => { saveDownloadedFile(file) },
  })

  function updateArtifact(index: number, next: ArtifactSpecPayload) {
    setArtifacts(artifacts.map((a, i) => (i === index ? next : a)))
  }

  return (
    <Card>
      <CardHeader
        title="SEF export"
        subtitle="An unsigned Surveillance Evidence Format bundle -- the manifest, ledger excerpt, and any listed artifact files."
      />
      <CardBody>
        <div className="grid gap-4">
          {artifacts.map((artifact, index) => (
            <div key={index} className="grid gap-3 rounded-lg border border-line p-4 sm:grid-cols-[1fr_2fr_2fr_auto]">
              <TextField
                label="Artifact ID"
                required
                value={artifact.artifact_id}
                onChange={(e) => { updateArtifact(index, { ...artifact, artifact_id: e.target.value }) }}
                placeholder="img1"
              />
              <TextField
                label="Source path"
                required
                value={artifact.source_path}
                onChange={(e) => { updateArtifact(index, { ...artifact, source_path: e.target.value }) }}
                placeholder="/evidence/disk1.img"
              />
              <TextField
                label="Description"
                value={artifact.description ?? ''}
                onChange={(e) => { updateArtifact(index, { ...artifact, description: e.target.value }) }}
              />
              <div className="flex items-end">
                <SecondaryButton
                  onClick={() => { setArtifacts(artifacts.filter((_, i) => i !== index)) }}
                >
                  Remove
                </SecondaryButton>
              </div>
            </div>
          ))}

          <div>
            <SecondaryButton onClick={() => { setArtifacts([...artifacts, { ...emptyArtifact }]) }}>
              Add artifact file
            </SecondaryButton>
          </div>

          <CheckboxField
            id="export-include-ledger"
            label="Include audit ledger excerpt"
            checked={includeLedger}
            onChange={setIncludeLedger}
          />

          {exportCase.isError && <ErrorBanner error={exportCase.error} />}

          <div className="flex justify-end">
            <PrimaryButton
              onClick={() => { exportCase.mutate() }}
              disabled={exportCase.isPending}
            >
              {exportCase.isPending ? 'Building bundle…' : 'Export SEF bundle'}
            </PrimaryButton>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
