// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReviewFilterItem } from '../api/types'
import { FilterTimeline } from './FilterTimeline'
import { SeekBar } from './player/SeekBar'
import { SkipNotice } from './player/SkipNotice'

afterEach(cleanup)

function filter(overrides: Partial<ReviewFilterItem> & Pick<ReviewFilterItem, 'id'>): ReviewFilterItem {
  return {
    category: 'violence',
    severity: 'strong',
    action: 'skip',
    start: 10,
    end: 20,
    text: null,
    note: null,
    confidence: 1,
    region: null,
    kept: false,
    ...overrides,
  }
}

describe('SkipNotice', () => {
  const notice = { ids: ['a'], seconds: 42, label: 'violence', notes: ['A fight breaks out'] }

  it('says what was skipped in the brand’s words', () => {
    render(<SkipNotice notice={notice} onKeepIn={() => undefined} />)
    expect(screen.getByRole('status').textContent).toContain('Skipped 42 s of violence')
  })

  it('explains on request and offers to keep it in', () => {
    const onKeepIn = vi.fn()
    render(<SkipNotice notice={notice} onKeepIn={onKeepIn} />)
    expect(screen.queryByText('A fight breaks out')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'What happened?' }))
    expect(screen.getByText('A fight breaks out')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Keep it in' }))
    expect(onKeepIn).toHaveBeenCalledOnce()
  })
})

describe('FilterTimeline', () => {
  it('draws one labeled lane per category present, in plain words', () => {
    render(
      <FilterTimeline
        duration={100}
        filters={[
          filter({ id: 'a' }),
          filter({ id: 'b', category: 'drugs_and_drinking', start: 50, end: 55 }),
        ]}
      />,
    )
    expect(screen.getByText('violence')).toBeTruthy()
    expect(screen.getByText('drugs and drinking')).toBeTruthy()
    expect(screen.queryByText('nudity')).toBeNull()
  })

  it('sizes blocks to their length and marks kept ones without relying on color', () => {
    const { container } = render(
      <FilterTimeline
        duration={100}
        filters={[filter({ id: 'a', start: 10, end: 30 }), filter({ id: 'b', start: 50, end: 60, kept: true })]}
      />,
    )
    const [first, second] = Array.from(container.querySelectorAll<HTMLElement>('.block'))
    expect(first.style.left).toBe('10%')
    expect(first.dataset.kept).toBe('false')
    expect(second.dataset.kept).toBe('true')
    expect(second.title).toContain('kept in')
  })

  it('says so when nothing is filtered', () => {
    render(<FilterTimeline duration={100} filters={[]} />)
    expect(screen.getByText('Nothing will be filtered.')).toBeTruthy()
  })
})

describe('SeekBar', () => {
  it('marks each moment with its category, so each shows in its own colour', () => {
    const { container } = render(
      <SeekBar
        time={0}
        duration={100}
        onSeek={() => undefined}
        filters={[
          filter({ id: 'a', category: 'nudity' }),
          filter({ id: 'b', category: 'swearing', start: 50, end: 51 }),
        ]}
      />,
    )
    const marks = Array.from(container.querySelectorAll<HTMLElement>('.seek-marks span'))
    expect(marks.map((m) => m.dataset.category)).toEqual(['swearing', 'nudity'])
    expect(marks[0].style.left).toBe('50%')
  })
})

describe('SeekBar overlaps', () => {
  const markOrder = (kinds: string[]) => {
    const { container } = render(
      <SeekBar
        time={0}
        duration={100}
        onSeek={() => undefined}
        // every kind covers the same stretch of the film
        filters={kinds.map((category, i) => filter({ id: String(i), category, start: 10, end: 20 }))}
      />,
    )
    return Array.from(container.querySelectorAll<HTMLElement>('.seek-marks span')).map((m) => m.dataset.category)
  }

  it('draws the worst kind last so it shows on top: nudity, sex scenes, violence, scary scenes', () => {
    const order = markOrder(['scary_scenes', 'violence', 'sexual_content', 'nudity'])
    expect(order).toEqual(['scary_scenes', 'violence', 'sexual_content', 'nudity'])
  })

  it('gives the same result whatever order the moments arrive in', () => {
    const order = markOrder(['sexual_content', 'nudity', 'scary_scenes', 'violence'])
    expect(order).toEqual(['scary_scenes', 'violence', 'sexual_content', 'nudity'])
  })
})
