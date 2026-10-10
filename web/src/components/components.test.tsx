// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReviewFilterItem } from '../api/types'
import { FilterTimeline } from './FilterTimeline'
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
    expect(screen.getByText('Nothing will be filtered for this profile.')).toBeTruthy()
  })
})
