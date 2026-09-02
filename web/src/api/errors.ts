/** Raised for any non-2xx response from the Pramaan API. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(`API request failed (${status}): ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}
