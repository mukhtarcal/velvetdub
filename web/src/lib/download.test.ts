import { describe, expect, it } from 'vitest'
import type { ExportState } from '../api/types'
import { copySummary, downloadControl } from './download'

function state(overrides: Partial<ExportState> = {}): ExportState {
  return {
    status: 'none',
    percent: 0,
    error: null,
    filename: 'Film (cleaned).mp4',
    size_bytes: null,
    output_seconds: 6128,
    removed_seconds: 192,
    cuts: 14,
    muted_words: 41,
    ...overrides,
  }
}

describe('copySummary', () => {
  it('says how long the copy will be and what was cut', () => {
    expect(copySummary(state())).toBe(
      'Your copy will be 1:42:08 long, 3 min 12 s shorter than the original: 14 scenes cut and 41 words muted.',
    )
  })

  it('uses singular words', () => {
    expect(copySummary(state({ cuts: 1, muted_words: 1, removed_seconds: 12 }))).toContain(
      '1 scene cut and 1 word muted',
    )
  })

  it('leaves out what is not happening', () => {
    expect(copySummary(state({ cuts: 0, removed_seconds: 0 }))).toBe(
      'Your copy will be 1:42:08 long: 41 words muted.',
    )
    expect(copySummary(state({ cuts: 0, muted_words: 0, removed_seconds: 0 }))).toBe(
      'Your copy will be 1:42:08 long. Nothing is cut.',
    )
  })

  it('says so when nothing would be left', () => {
    expect(copySummary(state({ output_seconds: 0 }))).toBe(
      'Everything is cut, so there is nothing left to save.',
    )
  })
})

describe('downloadControl', () => {
  it('starts the copy when none has been made', () => {
    const control = downloadControl(state())
    expect(control.action).toBe('start')
    expect(control.hint).toContain('The original stays as it is')
  })

  it('shows progress while it is being made', () => {
    const control = downloadControl(state({ status: 'working', percent: 37 }))
    expect(control.action).toBe('working')
    expect(control.hint).toContain('37%')
  })

  it('hands over the finished file, with its size', () => {
    const control = downloadControl(state({ status: 'ready', size_bytes: 1_900_000_000 }))
    expect(control).toMatchObject({ action: 'save', label: 'Download the cleaned movie' })
    expect(control.hint).toContain('1.9 GB')
  })

  it('offers to try again after a failure', () => {
    expect(downloadControl(state({ status: 'failed' })).action).toBe('retry')
  })

  it('cannot start when everything is cut', () => {
    expect(downloadControl(state({ output_seconds: 0 })).action).toBe('blocked')
  })
})
