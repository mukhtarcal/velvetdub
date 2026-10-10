import { describe, expect, it } from 'vitest'
import type { TitleSummary } from '../api/types'
import { titleStatus } from './titles'

function title(stages: Record<string, string>): TitleSummary {
  return { id: 't', name: 'T', created_at: '2026-01-01T00:00:00Z', duration: null, stages }
}

const ALL_DONE = {
  extract_audio: 'done',
  transcribe: 'done',
  visual_scan: 'done',
  translate: 'done',
  build_filters: 'done',
  subtitles: 'done',
}

describe('titleStatus', () => {
  it('is ready only when every step is done', () => {
    expect(titleStatus(title(ALL_DONE))).toEqual({ ready: true, label: 'Ready to watch' })
    expect(titleStatus(title({ ...ALL_DONE, subtitles: 'failed' })).ready).toBe(false)
  })

  it('says where it stopped, in plain words', () => {
    const status = titleStatus(title({ extract_audio: 'done', transcribe: 'failed' }))
    expect(status.label).toBe('Stopped at “transcribing the dialogue”')
  })

  it('describes partial and empty progress', () => {
    expect(titleStatus(title({})).label).toBe('Not processed yet')
    expect(titleStatus(title({ extract_audio: 'done', transcribe: 'done' })).label).toBe(
      'Partly processed (2 of 6 steps)',
    )
  })
})
