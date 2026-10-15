// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ExportState, ReviewFilterItem, ReviewInfo } from '@/api/types'
import { api } from '@/api/client'
import { DownloadView } from './DownloadView'

vi.mock('@/api/client', () => ({
  api: {
    review: vi.fn(),
    exportState: vi.fn(),
    startExport: vi.fn(),
    keepEvents: vi.fn(),
    exportFileUrl: (id: string) => `/api/titles/${id}/export/file`,
  },
}))

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function item(id: string, category: string, start: number, severity = 'strong'): ReviewFilterItem {
  return {
    id,
    category,
    severity,
    action: category === 'swearing' ? 'mute' : 'skip',
    start,
    end: start + 5,
    text: category === 'swearing' ? 'hell' : null,
    note: null,
    confidence: 1,
    region: null,
    kept: false,
  }
}

const review: ReviewInfo = {
  title_id: 't1',
  name: 'Harbor Lights 1947',
  duration: 100,
  filters: [item('a', 'nudity', 10), item('b', 'swearing', 50, 'mild')],
  runtime_removed: 5,
  scanned_categories: ['nudity', 'violence'],
}

function exportState(overrides: Partial<ExportState> = {}): ExportState {
  return {
    status: 'none',
    percent: 0,
    error: null,
    filename: 'Harbor Lights 1947 (cleaned).mp4',
    size_bytes: null,
    output_seconds: 95,
    removed_seconds: 5,
    cuts: 1,
    muted_words: 1,
    ...overrides,
  }
}

function renderPage() {
  return render(
    <DownloadView titleId="t1" />,
  )
}

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0) })

beforeEach(() => {
  vi.mocked(api.review).mockResolvedValue(review)
  vi.mocked(api.exportState).mockResolvedValue(exportState())
  vi.mocked(api.keepEvents).mockResolvedValue({ keep: [] })
})

describe('DownloadPage', () => {
  it('lists the cuts like the review does, with what the copy will be like', async () => {
    renderPage()
    expect(await screen.findByRole('tablist', { name: 'What to review' })).toBeTruthy()
    const tabs = screen.getAllByRole('tab', { selected: true }).map((t) => t.textContent)
    expect(tabs[0]).toContain('Scene filtering')
    expect(screen.queryByRole('tab', { name: /^Translation/ })).toBeNull() // not part of a download
    expect(screen.getByRole('region', { name: 'Overview' })).toBeTruthy()
    expect(
      await screen.findByText('Your copy will be 1:35 long, 5 s shorter than the original: 1 scene cut and 1 word muted.'),
    ).toBeTruthy()
    expect(screen.getByText(/original film is never changed/)).toBeTruthy()
  })

  it('has one main button, which starts making the copy', async () => {
    vi.mocked(api.startExport).mockResolvedValue(exportState({ status: 'working' }))
    renderPage()
    const button = await screen.findByRole('button', { name: 'Download the cleaned movie' })
    fireEvent.click(button)
    expect(vi.mocked(api.startExport)).toHaveBeenCalledWith('t1')
  })

  it('lets you leave a word level in, and then shows the copy that results', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Leave in all mild swearing' }))
    expect(vi.mocked(api.keepEvents)).toHaveBeenCalledWith('t1', ['b'], true)
    await vi.waitFor(() => expect(vi.mocked(api.exportState).mock.calls.length).toBeGreaterThan(1))
  })

  it('offers the finished file straight away when a matching copy is already saved', async () => {
    vi.mocked(api.exportState).mockResolvedValue(exportState({ status: 'ready', percent: 100, size_bytes: 2_100_000_000 }))
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    renderPage()
    const link = await screen.findByRole('link', { name: 'Download the cleaned movie' })
    expect(link.getAttribute('href')).toBe('/api/titles/t1/export/file')
    expect(link.getAttribute('download')).toBe('Harbor Lights 1947 (cleaned).mp4')
    expect(screen.getByText(/2\.1 GB/)).toBeTruthy()
    expect(clicked).not.toHaveBeenCalled() // you did not ask for it on this visit
  })

  it('shows progress, then downloads by itself when it finishes in front of you', async () => {
    vi.useFakeTimers()
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    vi.mocked(api.exportState)
      .mockResolvedValueOnce(exportState({ status: 'working', percent: 40 }))
      .mockResolvedValue(exportState({ status: 'ready', percent: 100, size_bytes: 1_000_000_000 }))
    renderPage()
    await flush()
    const bar = screen.getByRole('progressbar', { name: 'Making your copy' })
    expect(bar.getAttribute('aria-valuenow')).toBe('40')
    expect((screen.getByRole('button', { name: 'Making your copy…' }) as HTMLButtonElement).disabled).toBe(true)

    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(screen.getByRole('link', { name: 'Download the cleaned movie' })).toBeTruthy()
    expect(clicked).toHaveBeenCalledTimes(1)
  })

  it('says why it stopped and lets you try again', async () => {
    vi.mocked(api.exportState).mockResolvedValue(
      exportState({ status: 'failed', error: 'The copy could not be made: No such encoder' }),
    )
    renderPage()
    expect(await screen.findByText('The copy could not be made: No such encoder')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('cannot start when everything is cut', async () => {
    vi.mocked(api.exportState).mockResolvedValue(exportState({ output_seconds: 0, removed_seconds: 100 }))
    renderPage()
    const button = (await screen.findByRole('button', { name: 'Download the cleaned movie' })) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(within(document.body).getByText('Leave something in first.')).toBeTruthy()
  })
})
