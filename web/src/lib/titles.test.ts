import { describe, expect, it } from 'vitest'
import type { JobState, StageProgress, TitleSummary } from '../api/types'
import { cardStatus, choicesLine, currentStep, jobPercent } from './titles'

function title(stages: Record<string, string>): TitleSummary {
  return {
    id: 't',
    name: 'T',
    created_at: '2026-01-01T00:00:00Z',
    duration: null,
    stages,
    choices: null,
    scanned_categories: null,
  }
}

function job(status: JobState['status'], stages: Record<string, StageProgress>): JobState {
  return { title_id: 't', status, stages, error: null }
}

const ALL_DONE = {
  extract_audio: 'done',
  transcribe: 'done',
  visual_scan: 'done',
  translate: 'done',
  build_filters: 'done',
  subtitles: 'done',
}

describe('cardStatus', () => {
  it('is ready only when every step is done', () => {
    expect(cardStatus(title(ALL_DONE), null)).toEqual({ kind: 'ready' })
    expect(cardStatus(title({ ...ALL_DONE, subtitles: 'failed' }), null).kind).toBe('failed')
  })

  it('says where it stopped, in lower-case plain words', () => {
    const status = cardStatus(title({ extract_audio: 'done', translate: 'failed' }), null)
    expect(status).toEqual({ kind: 'failed', stage: 'translating' })
  })

  it('is idle when nothing was ever processed', () => {
    expect(cardStatus(title({}), null).kind).toBe('idle')
    expect(cardStatus(title({ extract_audio: 'done' }), null).kind).toBe('idle')
  })

  it('shows the live job over what the manifest recorded', () => {
    const running = job('running', {
      extract_audio: 'done',
      transcribe: 'done',
      visual_scan: 'running',
      translate: 'pending',
      build_filters: 'pending',
      subtitles: 'pending',
    })
    expect(cardStatus(title(ALL_DONE), running)).toEqual({
      kind: 'working',
      percent: 33,
      step: 'Scanning the picture',
    })
  })

  it('reports a failed job by the step that stopped', () => {
    const failed = job('failed', { extract_audio: 'done', transcribe: 'failed' })
    expect(cardStatus(title({}), failed)).toEqual({ kind: 'failed', stage: 'transcribing the dialogue' })
  })
})

describe('job progress', () => {
  it('counts skipped steps as done', () => {
    const states = { extract_audio: 'done', transcribe: 'skipped' } as const
    expect(jobPercent(job('running', states))).toBe(33)
  })

  it('names the step in progress, or says it is getting ready', () => {
    expect(currentStep(job('queued', {}))).toBe('Getting ready')
    expect(currentStep(job('running', { extract_audio: 'running' }))).toBe('Extracting the audio')
  })
})

describe('choicesLine', () => {
  it('lists the filters and subtitle languages that were chosen', () => {
    expect(
      choicesLine({ filter_categories: ['nudity', 'sexual_content'], subtitle_languages: ['en', 'es'] }),
    ).toBe('Skips nudity and sex scenes · Subtitles in English and Spanish')
  })

  it('says plainly when nothing was chosen', () => {
    expect(choicesLine({ filter_categories: [], subtitle_languages: ['ur'] })).toBe(
      'No filters · Subtitles in Urdu',
    )
    expect(choicesLine(null)).toBe('No filters · No subtitles')
  })
})
