// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JobState, ReviewInfo, TitleSummary } from '../api/types'
import { api } from '../api/client'
import { ProcessPage } from '../pages/ProcessPage'
import { Curtains } from './Curtains'
import { FilterTiles } from './FilterTiles'

vi.mock('../api/client', () => ({
  api: { titleSummary: vi.fn(), progress: vi.fn(), process: vi.fn(), review: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

const ALL = ['nudity', 'sexual_content', 'scary_scenes', 'violence'] as const

describe('FilterTiles', () => {
  it('starts with every tile off and says so in words', () => {
    render(<FilterTiles value={[]} onChange={() => undefined} available={[...ALL]} />)
    for (const tile of screen.getAllByRole('button')) expect(tile.getAttribute('aria-pressed')).toBe('false')
    expect(screen.getAllByText('Plays as is')).toHaveLength(4)
  })

  it('toggles a tile on and off', () => {
    const onChange = vi.fn()
    const { rerender } = render(<FilterTiles value={[]} onChange={onChange} available={[...ALL]} />)
    fireEvent.click(screen.getByRole('button', { name: /Nudity/ }))
    expect(onChange).toHaveBeenLastCalledWith(['nudity'])

    rerender(<FilterTiles value={['nudity']} onChange={onChange} available={[...ALL]} />)
    expect(screen.getByRole('button', { name: /Nudity/ }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('Will be skipped')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Nudity/ }))
    expect(onChange).toHaveBeenLastCalledWith([])
  })

  it('greys out what the scanner cannot check and says why', () => {
    render(<FilterTiles value={[]} onChange={() => undefined} available={['nudity', 'sexual_content']} />)
    expect((screen.getByRole('button', { name: /Violence/ }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: /Nudity/ }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByRole('note').textContent).toBe('This scanner can’t check for scary scenes and violence.')
  })
})

describe('Curtains', () => {
  it('is shut or open, and moves only when asked to', () => {
    const { container, rerender } = render(<Curtains open={false} animate />)
    const curtains = container.firstElementChild as HTMLElement
    expect(curtains.dataset.open).toBe('false')
    expect(curtains.dataset.animate).toBe('true')
    expect(curtains.getAttribute('aria-hidden')).toBe('true')

    rerender(<Curtains open animate />)
    expect(curtains.dataset.open).toBe('true')

    rerender(<Curtains open animate={false} />)
    expect(curtains.dataset.animate).toBe('false')
  })
})

function summary(stages: Record<string, string>): TitleSummary {
  return {
    id: 't1',
    name: 'Harbor Lights 1947',
    created_at: '2026-01-01T00:00:00Z',
    duration: 100,
    stages,
    choices: null,
    scanned_categories: [],
  }
}

const ALL_DONE = Object.fromEntries(
  ['extract_audio', 'transcribe', 'visual_scan', 'translate', 'build_filters', 'subtitles'].map((s) => [s, 'done']),
)

function job(status: JobState['status']): JobState {
  return { title_id: 't1', status, stages: {}, error: null }
}

const review: ReviewInfo = {
  title_id: 't1',
  name: 'Harbor Lights 1947',
  duration: 100,
  filters: [],
  runtime_removed: 0,
  scanned_categories: [],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/titles/t1/process']}>
      <Routes>
        <Route path="titles/:titleId/process" element={<ProcessPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const curtainsOf = (container: HTMLElement) => container.querySelector<HTMLElement>('.curtains')!

describe('ProcessPage curtains', () => {
  beforeEach(() => {
    vi.mocked(api.review).mockResolvedValue(review)
  })

  it('opens at once, without moving, when the title was already done', async () => {
    vi.mocked(api.titleSummary).mockResolvedValue(summary(ALL_DONE))
    vi.mocked(api.progress).mockRejectedValue(new Error('Nothing is processing for this title.'))
    const { container } = renderPage()
    expect(await screen.findByText('All set')).toBeTruthy()
    expect(curtainsOf(container).dataset.open).toBe('true')
    expect(curtainsOf(container).dataset.animate).toBe('false')
  })

  it('stays shut while working, then opens with movement when you watch it finish', async () => {
    vi.useFakeTimers()
    vi.mocked(api.titleSummary).mockResolvedValue(summary({}))
    vi.mocked(api.progress).mockResolvedValueOnce(job('running')).mockResolvedValue(job('done'))
    const { container } = renderPage()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByText('The projector is warming up')).toBeTruthy()
    expect(curtainsOf(container).dataset.open).toBe('false')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600)
    })
    expect(screen.getByText('All set')).toBeTruthy()
    expect(curtainsOf(container).dataset.open).toBe('true')
    expect(curtainsOf(container).dataset.animate).toBe('true')
  })

  it('keeps the curtains shut when processing failed', async () => {
    vi.mocked(api.titleSummary).mockResolvedValue(summary({}))
    vi.mocked(api.progress).mockResolvedValue({ ...job('failed'), error: 'The key ran out.' })
    const { container } = renderPage()
    expect(await screen.findByText('The key ran out.')).toBeTruthy()
    expect(curtainsOf(container).dataset.open).toBe('false')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('offers only Watch now when nothing was found to skip', async () => {
    vi.mocked(api.titleSummary).mockResolvedValue(summary(ALL_DONE))
    vi.mocked(api.progress).mockRejectedValue(new Error('none'))
    renderPage()
    expect(await screen.findByText('We found nothing to skip.')).toBeTruthy()
    expect(screen.queryByText('Review the cuts')).toBeNull()
    expect(screen.getByRole('link', { name: 'Watch now' }).className).toContain('primary')
  })
})
