import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

afterEach(() => vi.unstubAllGlobals())

// A fresh Response per call: a body can only be read once.
function stubFetch(body: string | null, status = 200) {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(body, { status })))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function lastHeaders(fetchMock: ReturnType<typeof vi.fn>): Headers {
  const init = fetchMock.mock.calls.at(-1)?.[1] as RequestInit | undefined
  return init?.headers as Headers
}

describe('api client', () => {
  it('returns parsed JSON on success', async () => {
    stubFetch('[]', 200)
    await expect(api.listTitles()).resolves.toEqual([])
  })

  it('uses the server’s message in the error', async () => {
    stubFetch(JSON.stringify({ detail: 'Title not found' }), 404)
    const error = await api.listTitles().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, message: 'Title not found' })
  })

  it('falls back to a generic message when the body is not JSON', async () => {
    stubFetch('boom', 500)
    await expect(api.listTitles()).rejects.toMatchObject({ message: 'Request failed (500)' })
  })

  it('sends the client header on state-changing requests only', async () => {
    const fetchMock = stubFetch('{"keep":["e1"]}', 200)
    await api.keepEvent('t1', 'e1')
    expect(lastHeaders(fetchMock).get('X-Velvetdub-Client')).toBe('web')

    await api.listTitles()
    expect(lastHeaders(fetchMock).get('X-Velvetdub-Client')).toBeNull()
  })

  it('sends JSON bodies with the right content type', async () => {
    const fetchMock = stubFetch('{"stages":{}}', 202)
    await api.process('t1', { subtitle_languages: ['en', 'es'], filter_categories: ['violence'] })
    const init = fetchMock.mock.calls.at(-1)?.[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      subtitle_languages: ['en', 'es'],
      filter_categories: ['violence'],
    })
    expect((init.headers as Headers).get('Content-Type')).toBe('application/json')
  })

  it('handles 204 responses', async () => {
    stubFetch(null, 204)
    await expect(api.editLine('t', 'es', 's0', 'hola')).resolves.toBeUndefined()
  })

  it('encodes path segments', async () => {
    const fetchMock = stubFetch('{}', 200)
    await api.playback('a/b')
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/titles/a%2Fb/playback')
  })
})
