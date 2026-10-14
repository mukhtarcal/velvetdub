import type { ScanCategory } from '../api/types'

/** The four picture filters, in the order they are offered. Hints are final copy (design README). */
export const FILTERS: { id: ScanCategory; label: string; hint: string }[] = [
  { id: 'nudity', label: 'Nudity', hint: 'Bare bodies, partial or full.' },
  { id: 'sexual_content', label: 'Sex scenes', hint: 'Sex scenes and sexual moments on screen.' },
  { id: 'scary_scenes', label: 'Scary scenes', hint: 'Jump scares and frightening images.' },
  { id: 'violence', label: 'Violence', hint: 'Fights, weapons, blood and injury.' },
]

/** Lower-case plain words for sentences ("sex scenes"), also for category ids from the server. */
export function filterWords(id: string): string {
  return FILTERS.find((f) => f.id === id)?.label.toLowerCase() ?? id.replace(/_/g, ' ')
}
