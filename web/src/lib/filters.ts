import type { FilterChoice, ScanCategory } from '../api/types'

export interface FilterDef {
  id: FilterChoice
  label: string
  hint: string
  /** What happens to what is found: moments in the picture are skipped, words are muted. */
  result: 'skipped' | 'muted'
}

/** Everything that can be chosen, in the order it is offered. Hints are final copy (design README). */
export const FILTERS: FilterDef[] = [
  { id: 'nudity', label: 'Nudity', hint: 'Bare bodies, partial or full.', result: 'skipped' },
  { id: 'sexual_content', label: 'Sex scenes', hint: 'Sex scenes and sexual moments on screen.', result: 'skipped' },
  { id: 'scary_scenes', label: 'Scary scenes', hint: 'Jump scares and frightening images.', result: 'skipped' },
  { id: 'violence', label: 'Violence', hint: 'Fights, weapons, blood and injury.', result: 'skipped' },
  { id: 'swearing', label: 'Swearing', hint: 'Swearing and crude words in the dialogue.', result: 'muted' },
]

export function isPicture(id: FilterChoice): id is ScanCategory {
  return id !== 'swearing'
}

/** The four that are scanned in the picture. */
export const PICTURE_FILTERS = FILTERS.filter((f): f is FilterDef & { id: ScanCategory } => isPicture(f.id))

/** Lower-case plain words for sentences ("sex scenes"), also for category ids from the server. */
export function filterWords(id: string): string {
  return FILTERS.find((f) => f.id === id)?.label.toLowerCase() ?? id.replace(/_/g, ' ')
}
