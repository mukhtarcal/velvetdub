import type { ScanCategory } from '../api/types'
import { joinLabels, sentenceCase } from './format'
import { FILTERS, filterWords } from './filters'
import { languageLabel } from './titles'

export interface AddTitleForm {
  hasFile: boolean
  name: string
  filters: ScanCategory[]
  subtitlesOn: boolean
  languages: string[]
}

/** Chosen filters in the order they are offered, whatever order they were ticked in. */
export function inFilterOrder(chosen: ScanCategory[]): ScanCategory[] {
  return FILTERS.map((f) => f.id).filter((id) => chosen.includes(id))
}

/** "Nudity and sex scenes", or a plain note when nothing is chosen. */
export function skipSummary(filters: ScanCategory[]): string {
  const words = inFilterOrder(filters).map(filterWords)
  return words.length ? sentenceCase(joinLabels(words)) : 'Nothing. The film plays as is.'
}

export function subtitleSummary(form: Pick<AddTitleForm, 'subtitlesOn' | 'languages'>): string {
  if (!form.subtitlesOn || form.languages.length === 0) return 'None'
  return joinLabels(form.languages.map(languageLabel))
}

/** Subtitles are on but no language is chosen: allowed while editing, but it blocks submit. */
export function needsLanguage(form: Pick<AddTitleForm, 'subtitlesOn' | 'languages'>): boolean {
  return form.subtitlesOn && form.languages.length === 0
}

export interface SubmitState {
  canSubmit: boolean
  /** Why submit is off, or what happens next when it is on. */
  hint: string
}

export function submitState(form: AddTitleForm): SubmitState {
  if (!form.hasFile) return { canSubmit: false, hint: 'Choose a file first.' }
  if (!form.name.trim()) return { canSubmit: false, hint: 'Give the title a name first.' }
  if (needsLanguage(form)) return { canSubmit: false, hint: 'Choose a subtitle language first.' }
  return { canSubmit: true, hint: 'Next, we upload the film and start the scan.' }
}

/** What is sent to the server. Subtitles off means no languages, whatever was ticked before. */
export function processChoices(form: Pick<AddTitleForm, 'filters' | 'subtitlesOn' | 'languages'>) {
  return {
    filter_categories: inFilterOrder(form.filters),
    subtitle_languages: form.subtitlesOn ? form.languages : [],
  }
}
