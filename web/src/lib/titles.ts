import { PIPELINE_STAGES, type TitleSummary } from '../api/types'

export interface TitleStatus {
  ready: boolean
  label: string
}

/** Plain description of how far along a title is. */
export function titleStatus(title: TitleSummary): TitleStatus {
  const states = PIPELINE_STAGES.map((s) => title.stages[s.id])
  const failedIndex = states.findIndex((s) => s === 'failed')
  if (failedIndex >= 0) {
    return { ready: false, label: `Stopped at “${PIPELINE_STAGES[failedIndex].label.toLowerCase()}”` }
  }
  const done = states.filter((s) => s === 'done').length
  if (done === PIPELINE_STAGES.length) return { ready: true, label: 'Ready to watch' }
  if (done === 0) return { ready: false, label: 'Not processed yet' }
  return { ready: false, label: `Partly processed (${done} of ${PIPELINE_STAGES.length} steps)` }
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
