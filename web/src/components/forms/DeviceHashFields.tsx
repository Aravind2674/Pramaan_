import { DEVICE_TYPES, HASH_ALGORITHMS } from '../../api/types'
import type { DeviceDetailsPayload, HashDeclarationPayload } from '../../api/types'
import { SelectField, TextField } from '../ui/form'

/** The device-details sub-form shared by the certificate's Part A and
 * Part B -- both name the same device, so both forms compose it rather
 * than duplicating five input fields. */
export function DeviceFields({
  value,
  onChange,
}: {
  value: DeviceDetailsPayload
  onChange: (next: DeviceDetailsPayload) => void
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SelectField
        label="Device type"
        required
        options={DEVICE_TYPES}
        value={value.device_type}
        onChange={(e) => { onChange({ ...value, device_type: e.target.value }) }}
      />
      {value.device_type === 'Other' && (
        <TextField
          label="Other device type"
          required
          value={value.other_device_type ?? ''}
          onChange={(e) => { onChange({ ...value, other_device_type: e.target.value }) }}
        />
      )}
      <TextField
        label="Make and model"
        required
        value={value.make_and_model}
        onChange={(e) => { onChange({ ...value, make_and_model: e.target.value }) }}
      />
      <TextField
        label="Serial number"
        value={value.serial_number ?? ''}
        onChange={(e) => { onChange({ ...value, serial_number: e.target.value }) }}
      />
      <TextField
        label="Identifier (IMEI/UID/MAC/Cloud ID)"
        value={value.identifier ?? ''}
        onChange={(e) => { onChange({ ...value, identifier: e.target.value }) }}
      />
    </div>
  )
}

export function HashFields({
  value,
  onChange,
}: {
  value: HashDeclarationPayload
  onChange: (next: HashDeclarationPayload) => void
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SelectField
        label="Hash algorithm"
        required
        options={HASH_ALGORITHMS}
        value={value.algorithm}
        onChange={(e) => { onChange({ ...value, algorithm: e.target.value }) }}
      />
      {value.algorithm === 'Other' && (
        <TextField
          label="Other algorithm name"
          required
          value={value.other_algorithm_name ?? ''}
          onChange={(e) => { onChange({ ...value, other_algorithm_name: e.target.value }) }}
        />
      )}
      <TextField
        label="Hash value"
        required
        className="font-mono-data"
        value={value.value}
        onChange={(e) => { onChange({ ...value, value: e.target.value }) }}
      />
    </div>
  )
}
