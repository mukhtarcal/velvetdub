import type { FilterItem } from '../api/types'
import { FilterEngine, type SkipRegion } from './FilterEngine'

export interface ControllerEvents {
  /** The playhead was moved past a skipped region. */
  onSkip: (region: SkipRegion) => void
  /** The set of blurred areas changed. */
  onBlurChange: (blurs: FilterItem[]) => void
}

/** The parts of an HTMLMediaElement the controller uses (lets tests pass a simple fake). */
export interface MediaLike extends EventTarget {
  currentTime: number
  muted: boolean
  paused: boolean
  duration: number
  playbackRate: number
  play(): Promise<void> | void
  pause(): void
}

type Frame = (callback: () => void) => number
type CancelFrame = (handle: number) => void

const DRIFT_LIMIT = 0.15

/**
 * Applies filters to a playing video: skips regions, mutes words, reports blurs.
 *
 * Checked every animation frame while playing (so a muted word is silenced precisely), and
 * after every seek. The video file is never modified.
 *
 * Phase 2 dubbing: `setExternalAudio` plays a separate audio file (the dub) in sync with the
 * video, which is then silent. Filters mute whichever one is audible.
 */
export class PlaybackController {
  private readonly video: MediaLike
  private readonly events: ControllerEvents
  private readonly requestFrame: Frame
  private readonly cancelFrame: CancelFrame
  private engine: FilterEngine
  private audio: MediaLike | null = null
  private userMuted = false
  private filterMuted = false
  private blurKey = ''
  private frame: number | null = null
  private running = false
  private readonly onEvent = () => this.tick()
  private readonly onPlay = () => {
    this.syncAudio()
    this.audio?.play()
    this.loop()
  }
  private readonly onPause = () => this.audio?.pause()

  constructor(
    video: MediaLike,
    engine: FilterEngine,
    events: ControllerEvents,
    requestFrame: Frame = (cb) => requestAnimationFrame(cb),
    cancelFrame: CancelFrame = (h) => cancelAnimationFrame(h),
  ) {
    this.video = video
    this.engine = engine
    this.events = events
    this.requestFrame = requestFrame
    this.cancelFrame = cancelFrame
  }

  start(): void {
    if (this.running) return
    this.running = true
    for (const name of ['seeked', 'timeupdate', 'loadedmetadata']) {
      this.video.addEventListener(name, this.onEvent)
    }
    this.video.addEventListener('play', this.onPlay)
    this.video.addEventListener('pause', this.onPause)
    if (!this.video.paused) this.loop()
    this.tick()
  }

  stop(): void {
    this.running = false
    for (const name of ['seeked', 'timeupdate', 'loadedmetadata']) {
      this.video.removeEventListener(name, this.onEvent)
    }
    this.video.removeEventListener('play', this.onPlay)
    this.video.removeEventListener('pause', this.onPause)
    if (this.frame !== null) this.cancelFrame(this.frame)
    this.frame = null
  }

  /** Swap in new filters (a different profile, or "Keep it in" was used). */
  setEngine(engine: FilterEngine): void {
    this.engine = engine
    this.tick()
  }

  /** The viewer's own mute button. Filters can additionally mute, never unmute. */
  setUserMuted(muted: boolean): void {
    this.userMuted = muted
    this.applyMute()
  }

  /** Play a separate audio track (a dub) instead of the video's own sound; null to go back. */
  setExternalAudio(audio: MediaLike | null): void {
    this.audio?.pause()
    this.audio = audio
    this.applyMute()
    if (audio) {
      this.syncAudio()
      if (!this.video.paused) void audio.play()
    }
  }

  /** One decision step. Public so tests (and seeks) can drive it directly. */
  tick(): void {
    const result = this.engine.evaluate(this.video.currentTime)

    if (result.skip) {
      this.video.currentTime = Math.min(result.skip.end, this.video.duration || result.skip.end)
      this.events.onSkip(result.skip)
      this.syncAudio()
    }

    this.filterMuted = result.muted
    this.applyMute()

    const key = result.blurs.map((b) => b.id).join('|')
    if (key !== this.blurKey) {
      this.blurKey = key
      this.events.onBlurChange(result.blurs)
    }

    if (this.audio && !this.video.paused) {
      if (Math.abs(this.audio.currentTime - this.video.currentTime) > DRIFT_LIMIT) this.syncAudio()
      this.audio.playbackRate = this.video.playbackRate
    }
  }

  private loop(): void {
    if (!this.running || this.frame !== null) return
    this.frame = this.requestFrame(() => {
      this.frame = null
      this.tick()
      if (!this.video.paused) this.loop()
    })
  }

  private syncAudio(): void {
    if (this.audio) this.audio.currentTime = this.video.currentTime
  }

  private applyMute(): void {
    const silent = this.userMuted || this.filterMuted
    if (this.audio) {
      this.video.muted = true
      this.audio.muted = silent
    } else {
      this.video.muted = silent
    }
  }
}
