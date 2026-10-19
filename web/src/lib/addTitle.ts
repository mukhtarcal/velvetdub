import type { FilterChoice } from '../api/types'
import { joinLabels, sentenceCase } from './format'
import { FILTERS, filterWords } from './filters'
import { languageLabel } from './titles'

export interface AddTitleForm {
  hasFile: boolean
  name: string
  filters: FilterChoice[]
  subtitlesOn: boolean
  languages: string[]
  dubbingOn: boolean
  dubLanguages: string[]
}

/** Chosen filters in the order they are offered, whatever order they were ticked in. */
export function inFilterOrder(chosen: FilterChoice[]): FilterChoice[] {
  return FILTERS.map((f) => f.id).filter((id) => chosen.includes(id))
}

/** "Nudity and swearing", or a plain note when nothing is chosen. */
export function skipSummary(filters: FilterChoice[]): string {
  const words = inFilterOrder(filters).map(filterWords)
  return words.length ? sentenceCase(joinLabels(words)) : 'Nothing. The film plays as is.'
}

export function subtitleSummary(form: Pick<AddTitleForm, 'subtitlesOn' | 'languages'>): string {
  if (!form.subtitlesOn || form.languages.length === 0) return 'None'
  return joinLabels(form.languages.map(languageLabel))
}

export function dubbingSummary(form: Pick<AddTitleForm, 'dubbingOn' | 'dubLanguages'>): string {
  if (!form.dubbingOn || form.dubLanguages.length === 0) return 'None'
  return joinLabels(form.dubLanguages.map(languageLabel))
}

/** Subtitles are on but no language is chosen: allowed while editing, but it blocks submit. */
export function needsLanguage(form: Pick<AddTitleForm, 'subtitlesOn' | 'languages'>): boolean {
  return form.subtitlesOn && form.languages.length === 0
}

/** The same for a dub. */
export function needsDubLanguage(form: Pick<AddTitleForm, 'dubbingOn' | 'dubLanguages'>): boolean {
  return form.dubbingOn && form.dubLanguages.length === 0
}

/** Whether anything at all was asked for. If not, the film is only stored: nothing is processed. */
export function choseAnything(
  form: Pick<AddTitleForm, 'filters' | 'subtitlesOn' | 'languages' | 'dubbingOn' | 'dubLanguages'>,
): boolean {
  return (
    form.filters.length > 0 ||
    (form.subtitlesOn && form.languages.length > 0) ||
    (form.dubbingOn && form.dubLanguages.length > 0)
  )
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
  if (needsDubLanguage(form)) return { canSubmit: false, hint: 'Choose a dubbing language first.' }
  if (!choseAnything(form)) {
    return { canSubmit: true, hint: 'Next, we upload the film. Nothing else is processed.' }
  }
  if (form.dubbingOn) {
    return { canSubmit: true, hint: 'Next, we upload the film and start processing. The dub is the slowest part.' }
  }
  return { canSubmit: true, hint: 'Next, we upload the film and start processing.' }
}

/** What is sent to the server. Subtitles or dubbing off means no languages, whatever was ticked before. */
export function processChoices(
  form: Pick<AddTitleForm, 'filters' | 'subtitlesOn' | 'languages' | 'dubbingOn' | 'dubLanguages'>,
) {
  return {
    filter_categories: inFilterOrder(form.filters),
    subtitle_languages: form.subtitlesOn ? form.languages : [],
    dub_languages: form.dubbingOn ? form.dubLanguages : [],
  }
}
