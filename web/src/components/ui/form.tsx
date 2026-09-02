import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'

const LABEL_CLASS = 'mb-1 block text-xs font-medium text-text-secondary'
const CONTROL_CLASS =
  'w-full rounded-md border border-line bg-surface-2 px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50'

interface FieldWrapperProps {
  label: string
  htmlFor: string
  required?: boolean
  hint?: string
  children: ReactNode
}

function FieldWrapper({ label, htmlFor, required, hint, children }: FieldWrapperProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className={LABEL_CLASS}>
        {label}
        {required === true && <span className="text-danger"> *</span>}
      </label>
      {children}
      {hint !== undefined && <p className="mt-1 text-xs text-text-muted">{hint}</p>}
    </div>
  )
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
}

export function TextField({ label, hint, id, required, className, ...rest }: TextFieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <FieldWrapper label={label} htmlFor={inputId} required={required} hint={hint}>
      <input
        id={inputId}
        required={required}
        className={className === undefined ? CONTROL_CLASS : `${CONTROL_CLASS} ${className}`}
        {...rest}
      />
    </FieldWrapper>
  )
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string
  hint?: string
}

export function TextAreaField({ label, hint, id, required, className, ...rest }: TextAreaFieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <FieldWrapper label={label} htmlFor={inputId} required={required} hint={hint}>
      <textarea
        id={inputId}
        required={required}
        className={className === undefined ? CONTROL_CLASS : `${CONTROL_CLASS} ${className}`}
        rows={3}
        {...rest}
      />
    </FieldWrapper>
  )
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  hint?: string
  options: readonly string[]
  placeholder?: string
}

export function SelectField({
  label,
  hint,
  id,
  required,
  options,
  placeholder,
  className,
  ...rest
}: SelectFieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <FieldWrapper label={label} htmlFor={inputId} required={required} hint={hint}>
      <select
        id={inputId}
        required={required}
        className={className === undefined ? CONTROL_CLASS : `${CONTROL_CLASS} ${className}`}
        {...rest}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </FieldWrapper>
  )
}

export function CheckboxField({
  label,
  checked,
  onChange,
  id,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  id: string
}) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm text-text-primary">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked)
        }}
        className="h-4 w-4 rounded border-line-strong bg-surface-2 text-accent focus:ring-accent"
      />
      {label}
    </label>
  )
}

export function PrimaryButton({
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
      {...rest}
    >
      {children}
    </button>
  )
}

export function SecondaryButton({
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 rounded-md border border-line-strong px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-50"
      {...rest}
    >
      {children}
    </button>
  )
}
