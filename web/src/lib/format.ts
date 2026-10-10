/** Runtime timestamp: 41:18, or 1:02:03 for long films. Used with tabular numerals. */
export function formatTime(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** Plain-language category names (docs/BRAND.md). */
const CATEGORY_LABELS: Record<string, string> = {
  swearing: 'swearing',
  blasphemy: 'blasphemy',
  nudity: 'nudity',
  sexual_content: 'sexual content',
  violence: 'violence',
  drugs_and_drinking: 'drugs and drinking',
  scary_scenes: 'scary scenes',
}

export const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS)

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replace(/_/g, ' ')
}

/** "violence", "violence and nudity", "violence, nudity and swearing". */
export function joinLabels(labels: string[]): string {
  const unique = [...new Set(labels)]
  if (unique.length <= 1) return unique[0] ?? ''
  return `${unique.slice(0, -1).join(', ')} and ${unique[unique.length - 1]}`
}
