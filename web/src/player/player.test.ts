import { describe, expect, it } from 'vitest'
import type { FilterItem } from '../api/types'
import { FilterEngine, type SkipRegion } from './FilterEngine'
import { PlaybackController, type MediaLike } from './PlaybackController'

function item(overrides: Partial<FilterItem> & Pick<FilterItem, 'id' | 'action'>): FilterItem {
  return {
    category: 'violence',
    severity: 'strong',
    start: 0,
    end: 1,
    text: null,
    note: null,
    confidence: 1,
    region: null,
    ...overrides,
  }
}

describe('FilterEngine', () => {
  it('skips inside a region and not at its end', () => {
    const engine = new FilterEngine([item({ id: 'a', action: 'skip', start: 10, end: 20 })])
    expect(engine.evaluate(9.9).skip).toBeNull()
    expect(engine.evaluate(10).skip?.end).toBe(20)
    expect(engine.evaluate(19.99).skip).not.toBeNull()
    expect(engine.evaluate(20).skip).toBeNull()
  })

  it('merges overlapping and touching skips into one jump', () => {
    const engine = new FilterEngine([
      item({ id: 'a', action: 'skip', start: 10, end: 20 }),
      item({ id: 'b', action: 'skip', start: 15, end: 30 }),
      item({ id: 'c', action: 'skip', start: 30.1, end: 40 }),
      item({ id: 'd', action: 'skip', start: 100, end: 110 }),
    ])
    expect(engine.skipRegions().map((r) => [r.start, r.end])).toEqual([
      [10, 40],
      [100, 110],
    ])
    expect(engine.evaluate(12).skip?.items.map((i) => i.id)).toEqual(['a', 'b', 'c'])
  })

  it('mutes a word with a little padding either side', () => {
    const engine = new FilterEngine([item({ id: 'w', action: 'mute', start: 5, end: 5.4 })])
    expect(engine.evaluate(4.8).muted).toBe(false)
    expect(engine.evaluate(4.95).muted).toBe(true)
    expect(engine.evaluate(5.45).muted).toBe(true)
    expect(engine.evaluate(5.6).muted).toBe(false)
  })

  it('treats replace like mute for audio, and reports blurs while active', () => {
    const engine = new FilterEngine([
      item({ id: 'r', action: 'replace', start: 1, end: 2 }),
      item({ id: 'b', action: 'blur', start: 3, end: 4 }),
    ])
    expect(engine.evaluate(1.5).muted).toBe(true)
    expect(engine.evaluate(3.5).blurs.map((b) => b.id)).toEqual(['b'])
    expect(engine.evaluate(3.5).muted).toBe(false)
    expect(engine.evaluate(5).blurs).toEqual([])
  })

  it('does nothing with no filters', () => {
    expect(new FilterEngine([]).evaluate(5)).toEqual({ muted: false, skip: null, blurs: [] })
  })
})

class FakeMedia extends EventTarget implements MediaLike {
  currentTime = 0
  muted = false
  paused = true
  duration = 100
  playbackRate = 1
  playCalls = 0
  play() {
    this.paused = false
    this.playCalls += 1
  }
  pause() {
    this.paused = true
  }
}

function setup(filters: FilterItem[]) {
  const video = new FakeMedia()
  const skips: SkipRegion[] = []
  const blurs: string[][] = []
  const controller = new PlaybackController(
    video,
    new FilterEngine(filters),
    { onSkip: (r) => skips.push(r), onBlurChange: (b) => blurs.push(b.map((x) => x.id)) },
    () => 0, // no animation frames in tests; we call tick() ourselves
    () => undefined,
  )
  controller.start()
  return { video, skips, blurs, controller }
}

describe('PlaybackController', () => {
  it('jumps past a skipped region once and reports it', () => {
    const { video, skips, controller } = setup([
      item({ id: 'a', action: 'skip', start: 10, end: 20 }),
    ])
    video.currentTime = 12
    controller.tick()
    expect(video.currentTime).toBe(20)
    expect(skips).toHaveLength(1)
    controller.tick()
    expect(skips).toHaveLength(1) // already past it
  })

  it('also skips when the viewer seeks into a region while paused', () => {
    const { video, skips } = setup([item({ id: 'a', action: 'skip', start: 10, end: 20 })])
    video.currentTime = 15
    video.dispatchEvent(new Event('seeked'))
    expect(video.currentTime).toBe(20)
    expect(skips).toHaveLength(1)
  })

  it('never seeks beyond the end of the video', () => {
    const { video, controller } = setup([item({ id: 'a', action: 'skip', start: 95, end: 130 })])
    video.currentTime = 96
    controller.tick()
    expect(video.currentTime).toBe(100)
  })

  it('mutes during a word and restores afterwards, respecting the viewer’s own mute', () => {
    const { video, controller } = setup([item({ id: 'w', action: 'mute', start: 5, end: 5.4 })])
    video.currentTime = 5.1
    controller.tick()
    expect(video.muted).toBe(true)
    video.currentTime = 7
    controller.tick()
    expect(video.muted).toBe(false)

    controller.setUserMuted(true)
    controller.tick()
    expect(video.muted).toBe(true) // a filter never un-mutes the viewer's choice
  })

  it('reports blur changes only when they change', () => {
    const { video, blurs, controller } = setup([
      item({ id: 'b', action: 'blur', start: 3, end: 4 }),
    ])
    video.currentTime = 3.5
    controller.tick()
    controller.tick()
    video.currentTime = 5
    controller.tick()
    expect(blurs).toEqual([['b'], []])
  })

  it('stops skipping once a detection is kept in (new engine)', () => {
    const { video, skips, controller } = setup([
      item({ id: 'a', action: 'skip', start: 10, end: 20 }),
    ])
    controller.setEngine(new FilterEngine([]))
    video.currentTime = 12
    controller.tick()
    expect(video.currentTime).toBe(12)
    expect(skips).toHaveLength(0)
  })

  it('plays a dub in sync and mutes the right element', () => {
    const { video, controller } = setup([item({ id: 'w', action: 'mute', start: 5, end: 6 })])
    const dub = new FakeMedia()
    video.paused = false
    video.currentTime = 4
    controller.setExternalAudio(dub)
    expect(video.muted).toBe(true) // the video's own sound is replaced by the dub
    expect(dub.currentTime).toBe(4)
    expect(dub.playCalls).toBe(1)

    video.currentTime = 5.5
    controller.tick()
    expect(dub.muted).toBe(true) // the filter mutes the dub
    expect(video.muted).toBe(true)
    expect(dub.currentTime).toBe(5.5) // drift corrected

    controller.setExternalAudio(null)
    video.currentTime = 8
    controller.tick()
    expect(video.muted).toBe(false) // back to the original track
  })

  it('stop() detaches its listeners', () => {
    const { video, skips, controller } = setup([
      item({ id: 'a', action: 'skip', start: 10, end: 20 }),
    ])
    controller.stop()
    video.currentTime = 12
    video.dispatchEvent(new Event('seeked'))
    expect(skips).toHaveLength(0)
  })
})
