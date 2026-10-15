import { PIPELINE_STAGES, type Choices, type JobState, type ProcessChoices, type TitleSummary } from '../api/types'
import { joinLabels } from './format'
import { filterWords } from './filters'

export type CardStatus =
  | { kind: 'ready' }
  | { kind: 'working'; percent: number; step: string }
  | { kind: 'failed'; stage: string }
  | { kind: 'idle' }

const ACTIVE = ['queued', 'running']

export function isActive(job: JobState | null | undefined): boolean {
  return !!job && ACTIVE.includes(job.status)
}

/** Share of the pipeline finished, from the live job. Skipped steps count as done. */
export function jobPercent(job: JobState): number {
  const done = PIPELINE_STAGES.filter((s) => ['done', 'skipped'].includes(job.stages[s.id])).length
  return Math.round((done / PIPELINE_STAGES.length) * 100)
}

/** The step running now, in plain words. */
export function currentStep(job: JobState): string {
  const running = PIPELINE_STAGES.find((s) => job.stages[s.id] === 'running')
  return running ? running.label : 'Getting ready'
}

/** Lower-case stage name for "Stopped while translating." */
function stageWords(label: string): string {
  return label.charAt(0).toLowerCase() + label.slice(1)
}

/** Where a title stands: the live job when there is one, otherwise what the manifest recorded. */
export function cardStatus(title: TitleSummary, job: JobState | null | undefined): CardStatus {
  if (job && isActive(job)) {
    return { kind: 'working', percent: jobPercent(job), step: currentStep(job) }
  }
  if (job?.status === 'failed') {
    const failed = PIPELINE_STAGES.find((s) => job.stages[s.id] === 'failed')
    return { kind: 'failed', stage: stageWords((failed ?? PIPELINE_STAGES[0]).label) }
  }
  const states = PIPELINE_STAGES.map((s) => title.stages[s.id])
  const failedIndex = states.findIndex((s) => s === 'failed')
  if (failedIndex >= 0) return { kind: 'failed', stage: stageWords(PIPELINE_STAGES[failedIndex].label) }
  if (states.every((s) => s === 'done')) return { kind: 'ready' }
  return { kind: 'idle' }
}

/** "Skips nudity and sex scenes · Subtitles in English and Spanish". */
export function choicesLine(choices: Choices | null): string {
  const filters = choices?.filter_categories ?? []
  const languages = choices?.subtitle_languages ?? []
  const skips = filters.length ? `Skips ${joinLabels(filters.map(filterWords))}` : 'No filters'
  const subs = languages.length
    ? `Subtitles in ${joinLabels(languages.map(languageLabel))}`
    : 'No subtitles'
  return `${skips} · ${subs}`
}

/** What was asked last time, to start processing again with the same choices. */
export function retryChoices(title: TitleSummary | null): ProcessChoices {
  return {
    subtitle_languages: title?.choices?.subtitle_languages ?? [],
    filter_categories: (title?.choices?.filter_categories ?? []) as ProcessChoices['filter_categories'],
  }
}

export const LANGUAGES: { code: string; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Spanish' },
  { code: 'fr', label: 'French' },
  { code: 'de', label: 'German' },
  { code: 'it', label: 'Italian' },
  { code: 'pt', label: 'Portuguese' },
  { code: 'ar', label: 'Arabic' },
  { code: 'ur', label: 'Urdu' },
  { code: 'hi', label: 'Hindi' },
  { code: 'tr', label: 'Turkish' },
  { code: 'ru', label: 'Russian' },
  { code: 'zh', label: 'Chinese' },
  { code: 'ja', label: 'Japanese' },
  { code: 'ko', label: 'Korean' },
]

export function languageLabel(code: string): string {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code
}
