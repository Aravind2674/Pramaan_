import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { NewCasePage } from './NewCasePage'

vi.mock('../api/client', () => ({
  api: {
    createCase: vi.fn(),
  },
}))

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/cases/new']}>
        <Routes>
          <Route path="/cases/new" element={ui} />
          <Route path="/cases/:caseId" element={<div>Case detail page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.createCase).mockReset()
})

describe('NewCasePage', () => {
  it('submits the form fields and navigates to the created case', async () => {
    vi.mocked(api.createCase).mockResolvedValue({
      case_id: 'sih-001',
      title: 'Sample',
      investigating_agency: 'Agency',
      examiner_name: 'Examiner',
      created_at: '2026-01-01T00:00:00Z',
    })

    const user = userEvent.setup()
    renderWithProviders(<NewCasePage />)

    await user.type(screen.getByLabelText(/case id/i), 'sih-001')
    await user.type(screen.getByLabelText(/^title/i), 'Sample')
    await user.type(screen.getByLabelText(/investigating agency/i), 'Agency')
    await user.type(screen.getByLabelText(/examiner name/i), 'Examiner')
    await user.click(screen.getByRole('button', { name: /create case/i }))

    await waitFor(() => {
      expect(api.createCase).toHaveBeenCalledWith({
        case_id: 'sih-001',
        title: 'Sample',
        investigating_agency: 'Agency',
        examiner_name: 'Examiner',
      })
    })
    await screen.findByText('Case detail page')
  })

  it('shows the server-supplied error instead of navigating on failure', async () => {
    const { ApiError } = await import('../api/errors')
    vi.mocked(api.createCase).mockRejectedValue(new ApiError(409, 'a case with ID already exists'))

    const user = userEvent.setup()
    renderWithProviders(<NewCasePage />)

    await user.type(screen.getByLabelText(/case id/i), 'dup')
    await user.type(screen.getByLabelText(/^title/i), 'Sample')
    await user.type(screen.getByLabelText(/investigating agency/i), 'Agency')
    await user.type(screen.getByLabelText(/examiner name/i), 'Examiner')
    await user.click(screen.getByRole('button', { name: /create case/i }))

    await screen.findByText('a case with ID already exists')
    expect(screen.queryByText('Case detail page')).not.toBeInTheDocument()
  })
})
