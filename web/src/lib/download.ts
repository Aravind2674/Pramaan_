import type { DownloadedFile } from '../api/client'

/** Saves a file the API returned (a certificate, case report, or SEF
 * bundle) to the user's disk via a throwaway object URL and anchor click
 * -- there is no server-side "generated reports" directory to link to,
 * since the API never writes those to disk in the first place. */
export function saveDownloadedFile(file: DownloadedFile): void {
  const url = URL.createObjectURL(file.blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = file.filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
