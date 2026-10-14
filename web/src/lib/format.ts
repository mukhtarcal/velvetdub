/** Runtime timestamp: 41:18, or 1:02:03 for long films. Used with tabular numerals. */
export function formatTime(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** File size in plain units: 2.4 GB, 640 MB. */
export function formatBytes(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`
  return `${Math.max(1, Math.round(bytes / 1e3))} KB`
}

/** Length of time for sentences: "3 min 12 s", "45 s", "1 h 2 min". */
export function formatDuration(totalSeconds: number): string {
  const seconds = Math.round(Math.max(0, totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return m > 0 ? `${h} h ${m} min` : `${h} h`
  if (m > 0) return s > 0 ? `${m} min ${s} s` : `${m} min`
  return `${s} s`
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

/** Worst first. Where moments overlap on the seek bar, the one earliest in this list shows. */
export const SEVERITY_ORDER = [
  'nudity',
  'sexual_content',
  'violence',
  'scary_scenes',
  'drugs_and_drinking',
  'blasphemy',
  'swearing',
]

/** Marks in the order to draw them: the worst last, so it sits on top of anything it overlaps. */
export function drawWorstLast<T extends { category: string }>(items: T[]): T[] {
  const rank = (c: string) => {
    const index = SEVERITY_ORDER.indexOf(c)
    return index === -1 ? SEVERITY_ORDER.length : index
  }
  return [...items].sort((a, b) => rank(b.category) - rank(a.category))
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replace(/_/g, ' ')
}

/** "violence", "violence and nudity", "violence, nudity and swearing". */
export function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function joinLabels(labels: string[]): string {
  const unique = [...new Set(labels)]
  if (unique.length <= 1) return unique[0] ?? ''
  return `${unique.slice(0, -1).join(', ')} and ${unique[unique.length - 1]}`
}
