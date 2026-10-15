// The only place that talks to the API. Adding auth later (a token, a 401 handler) is a change
// to `request` and `uploadTitle` here, nowhere else.

import type {
  Capabilities,
  ExportState,
  JobState,
  PlaybackInfo,
  ProcessChoices,
  ReviewInfo,
  ScriptLine,
  TitleSummary,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// The server refuses state-changing requests without this header, which blocks other web pages
// from driving the local API.
const CLIENT_HEADER = { 'X-Velvetdub-Client': 'web' }
const SAFE_METHODS = new Set(['GET', 'HEAD'])

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // not JSON; fall through
  }
  return `Request failed (${response.status})`
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init
  const method = (rest.method ?? 'GET').toUpperCase()
  const headers = new Headers(rest.headers)
  if (!SAFE_METHODS.has(method)) {
    for (const [key, value] of Object.entries(CLIENT_HEADER)) headers.set(key, value)
  }
  let body = rest.body
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  }
  const response = await fetch(`/api${path}`, { ...rest, method, headers, body })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const enc = encodeURIComponent

export const api = {
  listTitles: () => request<TitleSummary[]>('/titles'),
  /** One title's summary. The list is short and local, so this filters it rather than adding a route. */
  titleSummary: async (titleId: string) =>
    (await request<TitleSummary[]>('/titles')).find((t) => t.id === titleId) ?? null,
  exportState: (titleId: string) => request<ExportState>(`/titles/${enc(titleId)}/export`),
  startExport: (titleId: string) =>
    request<ExportState>(`/titles/${enc(titleId)}/export`, { method: 'POST' }),
  exportFileUrl: (titleId: string) => `/api/titles/${enc(titleId)}/export/file`,
  capabilities: () => request<Capabilities>('/capabilities'),
  playback: (titleId: string) => request<PlaybackInfo>(`/titles/${enc(titleId)}/playback`),
  review: (titleId: string) => request<ReviewInfo>(`/titles/${enc(titleId)}/review`),
  /** Keep in (or filter again) many moments at once, such as every mild word. */
  keepEvents: (titleId: string, eventIds: string[], keep: boolean) =>
    request<{ keep: string[] }>(`/titles/${enc(titleId)}/keep`, {
      method: 'PUT',
      json: { event_ids: eventIds, keep },
    }),
  keepEvent: (titleId: string, eventId: string) =>
    request<{ keep: string[] }>(`/titles/${enc(titleId)}/events/${enc(eventId)}/keep`, {
      method: 'PUT',
    }),
  filterEvent: (titleId: string, eventId: string) =>
    request<{ keep: string[] }>(`/titles/${enc(titleId)}/events/${enc(eventId)}/keep`, {
      method: 'DELETE',
    }),
  process: (titleId: string, choices: ProcessChoices) =>
    request<JobState>(`/titles/${enc(titleId)}/process`, { method: 'POST', json: choices }),
  progress: (titleId: string) => request<JobState>(`/titles/${enc(titleId)}/progress`),
  script: (titleId: string, language: string) =>
    request<ScriptLine[]>(`/titles/${enc(titleId)}/script/${enc(language)}`),
  editLine: (titleId: string, language: string, segmentId: string, text: string) =>
    request<void>(`/titles/${enc(titleId)}/script/${enc(language)}/${enc(segmentId)}`, {
      method: 'PUT',
      json: { text },
    }),
  importSubtitles: (titleId: string, language: string, content: string) =>
    request<{ lines: number }>(`/titles/${enc(titleId)}/subtitles/${enc(language)}/import`, {
      method: 'PUT',
      json: { content },
    }),
  subtitleDownloadUrl: (titleId: string, language: string, format: 'vtt' | 'srt', mask: boolean) =>
    `/api/titles/${enc(titleId)}/subtitles/${enc(language)}.${format}?download=true` +
    (mask ? '&mask=true' : ''),
}

/** Upload a film as the raw request body so a multi-gigabyte file is streamed, not buffered. */
export function uploadTitle(
  file: File,
  name: string,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<TitleSummary> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/titles?name=${enc(name)}&filename=${enc(file.name)}`)
    for (const [key, value] of Object.entries(CLIENT_HEADER)) xhr.setRequestHeader(key, value)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as TitleSummary)
      } else {
        let message = `Upload failed (${xhr.status})`
        try {
          const detail = (JSON.parse(xhr.responseText) as { detail?: unknown }).detail
          if (typeof detail === 'string') message = detail
        } catch {
          // keep the generic message
        }
        reject(new ApiError(xhr.status, message))
      }
    }
    xhr.onerror = () => reject(new ApiError(0, 'The upload was interrupted.'))
    xhr.onabort = () => reject(new ApiError(0, 'The upload was cancelled.'))
    signal?.addEventListener('abort', () => xhr.abort())
    xhr.send(file)
  })
}
