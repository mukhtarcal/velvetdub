// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import AddTitlePage from '@/app/(house)/page'

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/api/client', () => ({
  api: { capabilities: vi.fn() },
  uploadTitle: vi.fn(),
}))

afterEach(cleanup)

const SCAN = ['nudity', 'sexual_content', 'scary_scenes', 'violence'] as const

function offer(dub_languages: string[]) {
  vi.mocked(api.capabilities).mockResolvedValue({ scan_categories: [...SCAN], dub_languages })
}

const dubbingRow = () => screen.getByText('Dubbing', { selector: 'dt' }).nextElementSibling

describe('Add a title: dubbing', () => {
  it('is its own optional section, off until you add it', async () => {
    offer(['ar', 'es'])
    render(<AddTitlePage />)
    expect(screen.getByRole('heading', { name: 'Dubbing' })).toBeTruthy()
    const off = screen.getByRole('radio', { name: 'No dubbing' })
    expect(off.getAttribute('aria-checked')).toBe('true')
    await waitFor(() => expect((screen.getByRole('radio', { name: 'Add dubbing' }) as HTMLButtonElement).disabled).toBe(false))
    expect(screen.queryByRole('group', { name: 'Dubbing languages' })).toBeNull()
    expect(dubbingRow()?.textContent).toBe('None')
  })

  it('offers only the languages the voices can speak, and holds you to choosing one', async () => {
    offer(['ar', 'es'])
    render(<AddTitlePage />)
    await waitFor(() => expect((screen.getByRole('radio', { name: 'Add dubbing' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('radio', { name: 'Add dubbing' }))

    const group = await screen.findByRole('group', { name: 'Dubbing languages' })
    expect(Array.from(group.querySelectorAll('button')).map((b) => b.textContent)).toEqual(['Spanish', 'Arabic'])
    expect(screen.getByText('Choose at least one language, or pick No dubbing.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Arabic' }))
    expect(screen.getByRole('button', { name: 'Arabic' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.queryByText('Choose at least one language, or pick No dubbing.')).toBeNull()
    expect(dubbingRow()?.textContent).toBe('Arabic')
  })

  it('is independent of subtitles: the same language can be chosen for both', async () => {
    offer(['ar'])
    render(<AddTitlePage />)
    await waitFor(() => expect((screen.getByRole('radio', { name: 'Add dubbing' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('radio', { name: 'Add subtitles' }))
    fireEvent.click(screen.getByRole('radio', { name: 'Add dubbing' }))

    const subtitles = await screen.findByRole('group', { name: 'Subtitle languages' })
    const dubs = await screen.findByRole('group', { name: 'Dubbing languages' })
    fireEvent.click(within(subtitles).getByRole('button', { name: 'Arabic' }))
    fireEvent.click(within(dubs).getByRole('button', { name: 'Arabic' }))

    expect(screen.getByText('Subtitles', { selector: 'dt' }).nextElementSibling?.textContent).toBe('Arabic')
    expect(dubbingRow()?.textContent).toBe('Arabic')
  })

  it('says so in plain words, and cannot be turned on, when this computer cannot dub yet', async () => {
    offer([])
    render(<AddTitlePage />)
    expect(await screen.findByText('Dubbing isn’t set up on this computer yet.')).toBeTruthy()
    expect((screen.getByRole('radio', { name: 'Add dubbing' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not claim dubbing is missing while it is still asking', () => {
    vi.mocked(api.capabilities).mockReturnValue(new Promise(() => undefined))
    render(<AddTitlePage />)
    expect(screen.queryByText('Dubbing isn’t set up on this computer yet.')).toBeNull()
  })
})

describe('Add a title: filters', () => {
  const filtersRow = () => screen.getByText('Filters', { selector: 'dt' }).nextElementSibling

  it('offers swearing next to the four picture filters, always, whatever the scanner can check', async () => {
    vi.mocked(api.capabilities).mockResolvedValue({
      scan_categories: ['nudity', 'sexual_content'],
      dub_languages: [],
    })
    render(<AddTitlePage />)
    const swearing = await screen.findByRole('button', { name: /Swearing/ })
    await waitFor(() => expect((screen.getByRole('button', { name: /Violence/ }) as HTMLButtonElement).disabled).toBe(true))
    expect((swearing as HTMLButtonElement).disabled).toBe(false)
  })

  it('says nothing will be processed until something is chosen, then lists what was', async () => {
    offer([])
    render(<AddTitlePage />)
    expect(filtersRow()?.textContent).toBe('Nothing. The film plays as is.')
    fireEvent.click(screen.getByRole('button', { name: /Swearing/ }))
    fireEvent.click(screen.getByRole('button', { name: /Nudity/ }))
    expect(filtersRow()?.textContent).toBe('Nudity and swearing')
    expect(screen.getByRole('button', { name: /Swearing/ }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('Will be muted')).toBeTruthy()
  })

  it('explains that choosing nothing means the film is only stored', () => {
    offer([])
    render(<AddTitlePage />)
    expect(screen.getByText(/Choose nothing and the film is only stored/)).toBeTruthy()
  })
})
