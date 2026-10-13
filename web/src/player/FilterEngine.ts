import type { FilterItem } from '../api/types'

export interface SkipRegion {
  start: number
  end: number
  items: FilterItem[]
}

export interface Evaluation {
  /** Silence the audio right now. */
  muted: boolean
  /** Jump past this region, if the playhead is inside one. */
  skip: SkipRegion | null
  /** Parts of the picture to blur right now. */
  blurs: FilterItem[]
}

const DEFAULT_MUTE_LEAD = 0.25
const DEFAULT_MUTE_TAIL = 0.12

export interface EngineOptions {
  /**
   * Seconds muted before a word's stored start. Larger than the tail on purpose: transcript word
   * starts run a little late, and the audio you hear lags the playhead, so a mute that begins
   * exactly on the stored time lets the first part of the word through.
   */
  muteLead?: number
  /** Seconds muted after a word's stored end. */
  muteTail?: number
  /** Skips closer together than this are treated as one. */
  mergeGap?: number
}

/**
 * Turns the already-resolved filters for one viewer into per-moment decisions.
 *
 * It does no policy: the server decided which detections matter for this profile. The engine
 * only answers "what should happen at time t?" and is independent of any video element.
 */
export class FilterEngine {
  private readonly skips: SkipRegion[]
  private readonly mutes: FilterItem[]
  private readonly blurs: FilterItem[]
  private readonly lead: number
  private readonly tail: number

  constructor(filters: FilterItem[], options: EngineOptions = {}) {
    this.lead = options.muteLead ?? DEFAULT_MUTE_LEAD
    this.tail = options.muteTail ?? DEFAULT_MUTE_TAIL
    const mergeGap = options.mergeGap ?? 0.25

    this.mutes = filters.filter((f) => f.action === 'mute' || f.action === 'replace')
    this.blurs = filters.filter((f) => f.action === 'blur')
    this.skips = mergeSkips(
      filters.filter((f) => f.action === 'skip'),
      mergeGap,
    )
  }

  evaluate(time: number): Evaluation {
    return {
      muted: this.mutes.some((m) => time >= m.start - this.lead && time < m.end + this.tail),
      skip: this.skips.find((s) => time >= s.start && time < s.end) ?? null,
      blurs: this.blurs.filter((b) => time >= b.start && time < b.end),
    }
  }

  /** Every skipped region, for drawing marks on the seek bar. */
  skipRegions(): readonly SkipRegion[] {
    return this.skips
  }
}

function mergeSkips(items: FilterItem[], gap: number): SkipRegion[] {
  const sorted = [...items].sort((a, b) => a.start - b.start || a.end - b.end)
  const regions: SkipRegion[] = []
  for (const item of sorted) {
    const last = regions[regions.length - 1]
    if (last && item.start <= last.end + gap) {
      last.end = Math.max(last.end, item.end)
      last.items.push(item)
    } else {
      regions.push({ start: item.start, end: item.end, items: [item] })
    }
  }
  return regions
}
