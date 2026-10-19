// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PlaybackInfo, ReviewFilterItem, ReviewInfo } from '@/api/types'
import { api } from '@/api/client'
import { ReviewView } from './ReviewView'

vi.mock('@/api/client', () => ({
  api: {
    review: vi.fn(),
    playback: vi.fn(),
    keepEvents: vi.fn(),
    script: vi.fn(),
    keepEvent: vi.fn(),
    filterEvent: vi.fn(),
    subtitleDownloadUrl: vi.fn(() => '#'),
  },
}))

afterEach(cleanup)

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
  filters: [
    item('a', 'violence', 10),
    item('b', 'nudity', 30),
    item('c', 'swearing', 50, 'mild'),
    item('d', 'swearing', 60, 'moderate'),
    item('e', 'swearing', 70, 'mild'),
  ],
  runtime_removed: 10,
  scanned_categories: ['nudity', 'violence'],
}

beforeEach(() => {
  vi.mocked(api.review).mockResolvedValue(review)
  vi.mocked(api.keepEvents).mockResolvedValue({ keep: [] })
  vi.mocked(api.script).mockResolvedValue([])
  vi.mocked(api.playback).mockResolvedValue({
    subtitle_tracks: [
      { language: 'en', url: '' },
      { language: 'es', url: '' },
    ],
  } as PlaybackInfo)
})

function renderPage() {
  return render(
    <ReviewView titleId="t1" />,
  )
}

describe('ReviewPage swearing', () => {
  const openSwearing = async () => {
    renderPage()
    const tabs = await screen.findByRole('tablist', { name: 'What to review' })
    fireEvent.click(within(tabs).getByRole('tab', { name: /Swearing/ }))
  }

  it('says swearing was not checked when it was not chosen, instead of showing an empty list', async () => {
    vi.mocked(api.review).mockResolvedValue({ ...review, filters: [], swearing_checked: false })
    await openSwearing()
    expect(await screen.findByText(/Not checked for swearing/)).toBeTruthy()
    expect(screen.queryByText('Nothing found.')).toBeNull()
  })

  it('treats an older title, which has no answer, as checked', async () => {
    await openSwearing() // the shared fixture has no swearing_checked at all
    expect(screen.queryByText(/Not checked for swearing/)).toBeNull()
  })

  it('shows what was found when swearing was checked', async () => {
    vi.mocked(api.review).mockResolvedValue({ ...review, swearing_checked: true })
    await openSwearing()
    expect(screen.queryByText(/Not checked for swearing/)).toBeNull()
    expect(screen.getByRole('tablist', { name: 'Kind of language' })).toBeTruthy()
  })
})

describe('ReviewPage tabs', () => {
  it('reviews scenes, swearing and translation each on its own tab', async () => {
    renderPage()
    const tabs = await screen.findByRole('tablist', { name: 'What to review' })
    const names = within(tabs).getAllByRole('tab').map((t) => t.textContent)
    expect(names).toEqual(['Scene filtering (2)', 'Swearing (3)', 'Translation (2)'])
    expect(within(tabs).getByRole('tab', { selected: true }).textContent).toContain('Scene filtering')
    expect(screen.queryByText(/“hell”/)).toBeNull() // swearing is on its own tab
  })

  it('has one tab per kind of scene, showing only that kind', async () => {
    renderPage()
    const kinds = await screen.findByRole('tablist', { name: 'Kind of scene' })
    expect(within(kinds).getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Nudity (1)',
      'Sex scenes (0)',
      'Scary scenes (0)',
      'Violence (1)',
    ])
    expect(screen.getByText(/nudity \(strong\)/)).toBeTruthy()
    expect(screen.queryByText(/violence \(strong\)/)).toBeNull()

    fireEvent.click(within(kinds).getByRole('tab', { name: /Violence/ }))
    expect(screen.getByText(/violence \(strong\)/)).toBeTruthy()
    expect(screen.queryByText(/nudity \(strong\)/)).toBeNull()
  })

  it('says when a kind of scene was never scanned for', async () => {
    renderPage()
    const kinds = await screen.findByRole('tablist', { name: 'Kind of scene' })
    fireEvent.click(within(kinds).getByRole('tab', { name: /Sex scenes/ }))
    expect(screen.getByText(/Not checked for sex scenes/)).toBeTruthy()
  })

  it('shows swearing on its tab, split into swearing and blasphemy', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    const kinds = screen.getByRole('tablist', { name: 'Kind of language' })
    expect(within(kinds).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Swearing (3)', 'Blasphemy (0)'])
    expect(screen.queryByText(/“hell”/)).toBeNull() // each level is closed until you open it
    for (const level of ['Moderate', 'Mild']) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${level}`) }))
    }
    expect(screen.getAllByText(/“hell”/)).toHaveLength(3)
  })

  it('lists a tab for each subtitle language, and moves between tabs with the arrow keys', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Translation/ }))
    const languages = screen.getByRole('tablist', { name: 'Language' })
    const [english, spanish] = within(languages).getAllByRole('tab')
    expect(english.textContent).toBe('English')
    fireEvent.keyDown(english, { key: 'ArrowRight' })
    expect(spanish.getAttribute('aria-selected')).toBe('true')
    expect(vi.mocked(api.script)).toHaveBeenCalledWith('t1', 'es')
  })
})

describe('ReviewPage overview', () => {
  it('has no filter profile to choose', async () => {
    renderPage()
    await screen.findByRole('tablist', { name: 'What to review' })
    expect(screen.queryByText(/profile/i)).toBeNull()
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('shows every cut on one timeline, a lane per kind in its own colour', async () => {
    renderPage()
    const overview = (await screen.findByRole('region', { name: 'Overview' })) as HTMLElement
    const lanes = Array.from(overview.querySelectorAll<HTMLElement>('.lane[data-category]'))
    expect(lanes.map((l) => l.dataset.category).sort()).toEqual(['nudity', 'swearing', 'violence'])
    expect(within(overview).getByText('swearing')).toBeTruthy() // each lane is named, not just coloured
    expect(overview.querySelectorAll('.swatch')).toHaveLength(3)
    expect(overview.textContent).toContain('Removes')
  })
})

describe('ReviewPage leave in', () => {
  it('groups swearing by severity, strongest first, with moderates together', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    const groups = screen.getAllByRole('region').filter((r) => /(strong|moderate|mild) swearing/.test(r.getAttribute('aria-label') ?? ''))
    expect(groups.map((g) => g.getAttribute('aria-label'))).toEqual(['moderate swearing', 'mild swearing'])
    const mild = groups[1]
    expect(within(mild).queryByText(/“hell”/)).toBeNull()
    fireEvent.click(within(mild).getByRole('button', { name: /^Mild/ }))
    expect(within(mild).getAllByText(/“hell”/)).toHaveLength(2)
    fireEvent.click(within(mild).getByRole('button', { name: /^Mild/ }))
    expect(within(mild).queryByText(/“hell”/)).toBeNull()
  })

  it('drops down the strong and moderate groups too, each on its own', async () => {
    vi.mocked(api.review).mockResolvedValue({
      ...review,
      filters: [...review.filters, item('f', 'swearing', 80, 'strong')],
    })
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    const strong = screen.getByRole('button', { name: /^Strong/ })
    expect(strong.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(strong)
    expect(strong.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getAllByText(/“hell”/)).toHaveLength(1) // only the strong one is open
    expect(screen.getByRole('button', { name: /^Moderate/ }).getAttribute('aria-expanded')).toBe('false')
  })

  it('leaves a whole severity level in with one click', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Leave in all mild swearing' }))
    expect(vi.mocked(api.keepEvents)).toHaveBeenCalledWith('t1', ['c', 'e'], true)
  })

  it('leaves a whole kind of scene in', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Leave in all nudity' }))
    expect(vi.mocked(api.keepEvents)).toHaveBeenCalledWith('t1', ['b'], true)
  })

  it('offers the way back once everything in a group is left in', async () => {
    vi.mocked(api.review).mockResolvedValue({
      ...review,
      filters: review.filters.map((f) => (f.severity === 'mild' ? { ...f, kept: true } : f)),
    })
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: /^Swearing/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Filter again all mild swearing' }))
    expect(vi.mocked(api.keepEvents)).toHaveBeenCalledWith('t1', ['c', 'e'], false)
  })

  it('leaves in one moment on its own', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Keep it in' }))
    expect(vi.mocked(api.keepEvents)).toHaveBeenCalledWith('t1', ['b'], true)
  })
})
