import { describe, expect, it } from 'vitest'
import { DUBBING_STAGES, PIPELINE_STAGES, stagesFor, type JobState, type StageProgress, type TitleSummary } from '../api/types'
import { cardStatus, choicesLine, currentStep, jobPercent, retryChoices, shownStages, wantsDub } from './titles'

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

const DUB_DONE = Object.fromEntries(DUBBING_STAGES.map((s) => [s.id, 'done']))

describe('a title that was asked to be dubbed', () => {
  const dubbed = (stages: Record<string, string>): TitleSummary => ({
    ...title(stages),
    choices: { filter_categories: [], subtitle_languages: [], dub_languages: ['ar'] },
  })

  it('lists the dub steps only for such a title', () => {
    expect(stagesFor(false)).toEqual(PIPELINE_STAGES)
    expect(stagesFor(true).map((s) => s.id).slice(-6)).toEqual([
      'separate',
      'dub_transcribe',
      'dub_translate',
      'dub_voices',
      'dub_speech',
      'dub_mix',
    ])
    expect(wantsDub(null)).toBe(false)
    expect(wantsDub({ filter_categories: [], subtitle_languages: [] })).toBe(false) // an older title
    expect(wantsDub({ filter_categories: [], subtitle_languages: [], dub_languages: ['ar'] })).toBe(true)
  })

  it('is not ready until the dub is finished too', () => {
    expect(cardStatus(dubbed(ALL_DONE), null).kind).toBe('idle')
    expect(cardStatus(dubbed({ ...ALL_DONE, ...DUB_DONE }), null)).toEqual({ kind: 'ready' })
  })

  it('leaves an older title ready, though it has no dub steps recorded', () => {
    expect(cardStatus(title(ALL_DONE), null)).toEqual({ kind: 'ready' })
  })

  it('says where the dub stopped', () => {
    const status = cardStatus(dubbed({ ...ALL_DONE, separate: 'done', dub_speech: 'failed' }), null)
    expect(status).toEqual({ kind: 'failed', stage: 'recording the dub' })
  })

  it('counts progress over the longer list while the dub is made', () => {
    const states = Object.fromEntries(PIPELINE_STAGES.map((s) => [s.id, 'done'])) as Record<string, StageProgress>
    const running = job('running', { ...states, separate: 'running' })
    expect(jobPercent(running, stagesFor(true))).toBe(50)
    expect(currentStep(running, stagesFor(true))).toBe('Separating voices from the music')
  })

  it('counts a dub-only title over the dub steps alone, since nothing else was asked for', () => {
    const running = job('running', { separate: 'done', dub_transcribe: 'running' })
    expect(cardStatus(dubbed({}), running)).toEqual({
      kind: 'working',
      percent: 17,
      step: 'Listening to the voices alone',
    })
  })

  it('is started again with the same languages', () => {
    expect(retryChoices(dubbed({})).dub_languages).toEqual(['ar'])
    expect(retryChoices(title({})).dub_languages).toEqual([])
  })
})

describe('shownStages', () => {
  const chosen = (filters: string[], subs: string[] = [], dubs: string[] = []) => ({
    filter_categories: filters,
    subtitle_languages: subs,
    dub_languages: dubs,
  })
  const ids = (choices: ReturnType<typeof chosen> | null) => shownStages(choices).map((s) => s.id)

  it('shows no steps when nothing was chosen, since the film is only stored', () => {
    expect(ids(chosen([]))).toEqual([])
  })

  it('shows the usual steps while the choices are not known yet', () => {
    expect(shownStages(null)).toEqual(PIPELINE_STAGES)
  })

  it('shows the transcription and filter timeline for swearing, and no picture scan or translation', () => {
    expect(ids(chosen(['swearing']))).toEqual(['extract_audio', 'transcribe', 'build_filters'])
  })

  it('shows the picture scan and filter timeline, with no transcription, for a scene filter', () => {
    expect(ids(chosen(['violence']))).toEqual(['visual_scan', 'build_filters'])
  })

  it('shows transcription, translation and subtitles for subtitles, but no filter timeline', () => {
    expect(ids(chosen([], ['es']))).toEqual(['extract_audio', 'transcribe', 'translate', 'subtitles'])
  })

  it('shows only the dub steps for a dub alone: the film is not transcribed for it', () => {
    expect(ids(chosen([], [], ['ar']))).toEqual(DUBBING_STAGES.map((s) => s.id))
  })

  it('shows everything when everything was chosen', () => {
    expect(ids(chosen(['nudity', 'swearing'], ['en'], ['ar']))).toEqual(stagesFor(true).map((s) => s.id))
  })
})

describe('choicesLine', () => {
  it('says swearing is muted, not skipped', () => {
    expect(choicesLine({ filter_categories: ['violence', 'swearing'], subtitle_languages: [] })).toBe(
      'Skips violence · Mutes swearing · No subtitles',
    )
    expect(choicesLine({ filter_categories: ['swearing'], subtitle_languages: [] })).toBe(
      'Mutes swearing · No subtitles',
    )
  })

  it('lists the filters and subtitle languages that were chosen', () => {
    expect(
      choicesLine({ filter_categories: ['nudity', 'sexual_content'], subtitle_languages: ['en', 'es'] }),
    ).toBe('Skips nudity and sex scenes · Subtitles in English and Spanish')
  })

  it('adds the dub only when there is one', () => {
    const choices = { filter_categories: [], subtitle_languages: ['en'], dub_languages: ['ar'] }
    expect(choicesLine(choices)).toBe('No filters · Subtitles in English · Dubbed in Arabic')
    expect(choicesLine({ ...choices, dub_languages: [] })).toBe('No filters · Subtitles in English')
  })

  it('says plainly when nothing was chosen', () => {
    expect(choicesLine({ filter_categories: [], subtitle_languages: ['ur'] })).toBe(
      'No filters · Subtitles in Urdu',
    )
    expect(choicesLine(null)).toBe('No filters · No subtitles')
  })
})
