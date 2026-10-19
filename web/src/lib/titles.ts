import { PIPELINE_STAGES, stagesFor, type Choices, type FilterChoice, type JobState, type ProcessChoices, type StageInfo, type TitleSummary } from '../api/types'
import { joinLabels } from './format'
import { filterWords, isPicture } from './filters'

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
export function jobPercent(job: JobState, stages: StageInfo[] = PIPELINE_STAGES): number {
  // With nothing to do there are no steps to count: it is finished as soon as the job is.
  if (stages.length === 0) return job.status === 'done' ? 100 : 0
  const done = stages.filter((s) => ['done', 'skipped'].includes(job.stages[s.id])).length
  return Math.round((done / stages.length) * 100)
}

/** The steps to show for a title: only the ones its choices actually make work to do. A title
 * with nothing chosen shows none, since it is only stored. Every step still runs and is recorded
 * (those without work finish at once), so readiness is judged on `stagesFor`, not on this. */
export function shownStages(choices: Choices | null | undefined): StageInfo[] {
  if (!choices) return PIPELINE_STAGES // not known yet: show the usual steps
  const picture = choices.filter_categories.some((c) => isPicture(c as FilterChoice))
  const swearing = choices.filter_categories.includes('swearing')
  const subtitles = choices.subtitle_languages.length > 0
  const needed: Record<string, boolean> = {
    extract_audio: swearing || subtitles,
    transcribe: swearing || subtitles,
    visual_scan: picture,
    translate: subtitles,
    build_filters: picture || swearing,
    subtitles,
  }
  return stagesFor(wantsDub(choices)).filter((s) => needed[s.id] ?? true)
}

/** Whether a dub was asked for, which decides which steps are listed. */
export function wantsDub(choices: Choices | null | undefined): boolean {
  return (choices?.dub_languages ?? []).length > 0
}

/** The step running now, in plain words. */
export function currentStep(job: JobState, stages: StageInfo[] = PIPELINE_STAGES): string {
  const running = stages.find((s) => job.stages[s.id] === 'running')
  return running ? running.label : 'Getting ready'
}

/** Lower-case stage name for "Stopped while translating." */
function stageWords(label: string): string {
  return label.charAt(0).toLowerCase() + label.slice(1)
}

/** Where a title stands: the live job when there is one, otherwise what the manifest recorded. */
export function cardStatus(title: TitleSummary, job: JobState | null | undefined): CardStatus {
  const stages = stagesFor(wantsDub(title.choices))
  if (job && isActive(job)) {
    const shown = shownStages(title.choices)
    return { kind: 'working', percent: jobPercent(job, shown), step: currentStep(job, shown) }
  }
  if (job?.status === 'failed') {
    const failed = stages.find((s) => job.stages[s.id] === 'failed')
    return { kind: 'failed', stage: stageWords((failed ?? stages[0]).label) }
  }
  const states = stages.map((s) => title.stages[s.id])
  const failedIndex = states.findIndex((s) => s === 'failed')
  if (failedIndex >= 0) return { kind: 'failed', stage: stageWords(stages[failedIndex].label) }
  if (states.every((s) => s === 'done')) return { kind: 'ready' }
  return { kind: 'idle' }
}

/** "Skips nudity and sex scenes · Mutes swearing · Subtitles in English and Spanish · Dubbed in
 * Arabic". The dub is mentioned only when there is one. */
export function choicesLine(choices: Choices | null): string {
  const filters = choices?.filter_categories ?? []
  const languages = choices?.subtitle_languages ?? []
  const dubs = choices?.dub_languages ?? []
  const scenes = filters.filter((f) => isPicture(f as FilterChoice))
  const filterParts = [
    scenes.length ? `Skips ${joinLabels(scenes.map(filterWords))}` : '',
    filters.includes('swearing') ? 'Mutes swearing' : '',
  ].filter(Boolean)
  const skips = filterParts.length ? filterParts.join(' · ') : 'No filters'
  const subs = languages.length
    ? `Subtitles in ${joinLabels(languages.map(languageLabel))}`
    : 'No subtitles'
  const parts = [skips, subs]
  if (dubs.length) parts.push(`Dubbed in ${joinLabels(dubs.map(languageLabel))}`)
  return parts.join(' · ')
}

/** What was asked last time, to start processing again with the same choices. */
export function retryChoices(title: TitleSummary | null): ProcessChoices {
  return {
    subtitle_languages: title?.choices?.subtitle_languages ?? [],
    dub_languages: title?.choices?.dub_languages ?? [],
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
