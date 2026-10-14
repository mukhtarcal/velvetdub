import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FilterItem, PlaybackInfo } from '../../api/types'
import { categoryLabel, formatTime, joinLabels } from '../../lib/format'
import { languageLabel } from '../../lib/titles'
import { FilterEngine, type SkipRegion } from '../../player/FilterEngine'
import { PlaybackController } from '../../player/PlaybackController'
import { FullScreenIcon, PauseIcon, PlayIcon, RewindIcon, VolumeIcon } from '../Icons'
import { FlagMoment } from './FlagMoment'
import { SeekBar } from './SeekBar'
import { SkipNotice, type SkipNoticeData } from './SkipNotice'
import './player.css'

const NOTICE_MS = 9000

interface Props {
  info: PlaybackInfo
  /** Persist "Keep it in" for these detections. */
  onKeep: (eventIds: string[]) => Promise<void>
}

function noticeFor(region: SkipRegion): SkipNoticeData {
  return {
    ids: region.items.map((i) => i.id),
    seconds: Math.round(region.end - region.start),
    label: joinLabels(region.items.map((i) => categoryLabel(i.category))),
    notes: region.items.map((i) => i.note).filter((n): n is string => Boolean(n)),
  }
}

export function Player({ info, onKeep }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const controller = useRef<PlaybackController | null>(null)
  const audioElement = useRef<HTMLAudioElement | null>(null)

  const [keptNow, setKeptNow] = useState<ReadonlySet<string>>(new Set())
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(info.duration ?? 0)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [notice, setNotice] = useState<{ data: SkipNoticeData; start: number } | null>(null)
  const [blurs, setBlurs] = useState<FilterItem[]>([])
  const [subtitleLanguage, setSubtitleLanguage] = useState<string>(
    info.subtitle_tracks[0]?.language ?? 'off',
  )
  const [audioTrackId, setAudioTrackId] = useState(info.audio_tracks[0]?.id ?? '')
  const [flagging, setFlagging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeFilters = useMemo(
    () => info.filters.filter((f) => !keptNow.has(f.id)),
    [info.filters, keptNow],
  )
  const engine = useMemo(() => new FilterEngine(activeFilters), [activeFilters])

  // New filters from the server already include what was kept in, so local choices reset.
  useEffect(() => setKeptNow(new Set()), [info])

  // Create the controller once per video element, then hand it new engines as they change.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const created = new PlaybackController(video, engine, {
      onSkip: (region) => setNotice({ data: noticeFor(region), start: region.start }),
      onBlurChange: setBlurs,
    })
    controller.current = created
    created.start()
    return () => {
      created.stop()
      controller.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- engine updates are handled below
  }, [])

  useEffect(() => controller.current?.setEngine(engine), [engine])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), NOTICE_MS)
    return () => window.clearTimeout(timer)
  }, [notice])

  // Show the chosen subtitle language, hide the rest.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    for (const track of Array.from(video.textTracks)) {
      track.mode = track.language === subtitleLanguage ? 'showing' : 'disabled'
    }
  }, [subtitleLanguage, info.subtitle_tracks])

  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) void video.play()
    else video.pause()
  }, [])

  const seekBy = useCallback((delta: number) => {
    const video = videoRef.current
    if (video) video.currentTime = Math.max(0, video.currentTime + delta)
  }, [])

  const toggleMute = useCallback(() => {
    setMuted((current) => {
      controller.current?.setUserMuted(!current)
      return !current
    })
  }, [])

  const toggleFullScreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen()
    else void stageRef.current?.requestFullscreen()
  }, [])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement
      if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return
      if (event.key === ' ' || event.key === 'k') {
        event.preventDefault()
        togglePlay()
      } else if (event.key === 'ArrowLeft') seekBy(-10)
      else if (event.key === 'ArrowRight') seekBy(10)
      else if (event.key === 'm') toggleMute()
      else if (event.key === 'f') toggleFullScreen()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [togglePlay, seekBy, toggleMute, toggleFullScreen])

  async function keepIn() {
    const video = videoRef.current
    if (!notice || !video) return
    const ids = notice.data.ids
    const next = new Set([...keptNow, ...ids])
    setKeptNow(next)
    // Update the engine before seeking back, or the playhead would be skipped again.
    controller.current?.setEngine(new FilterEngine(info.filters.filter((f) => !next.has(f.id))))
    video.currentTime = notice.start
    setNotice(null)
    try {
      await onKeep(ids)
    } catch {
      setError('Could not save that choice, so it will apply to this viewing only.')
    }
  }

  function chooseAudio(trackId: string) {
    setAudioTrackId(trackId)
    const track = info.audio_tracks.find((t) => t.id === trackId)
    audioElement.current?.pause()
    audioElement.current = null
    if (!track || track.kind === 'original') {
      controller.current?.setExternalAudio(null)
      return
    }
    const element = new Audio(track.url)
    audioElement.current = element
    controller.current?.setExternalAudio(element)
  }

  function openFlag() {
    videoRef.current?.pause()
    setFlagging(true)
  }

  return (
    <section className="player" aria-label={`Player: ${info.name}`}>
      <div className="stage" ref={stageRef}>
        <video
          ref={videoRef}
          src={info.source_url}
          playsInline
          preload="metadata"
          onClick={togglePlay}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        >
          {info.subtitle_tracks.map((track) => (
            <track
              key={track.language}
              kind="subtitles"
              src={track.url}
              srcLang={track.language}
              label={languageLabel(track.language)}
            />
          ))}
        </video>

        {blurs.map((b) => (
          <div
            key={b.id}
            className="blur-layer"
            aria-hidden="true"
            style={
              b.region
                ? {
                    left: `${b.region.x * 100}%`,
                    top: `${b.region.y * 100}%`,
                    width: `${b.region.width * 100}%`,
                    height: `${b.region.height * 100}%`,
                  }
                : { inset: 0 }
            }
          />
        ))}

        {notice && <SkipNotice notice={notice.data} onKeepIn={() => void keepIn()} />}
      </div>

      <div className="controls">
        <SeekBar
          time={time}
          duration={duration}
          filters={activeFilters}
          onSeek={(seconds) => {
            if (videoRef.current) videoRef.current.currentTime = seconds
          }}
        />
        <div className="control-row">
          <button type="button" className="icon-button" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
            {playing ? <PauseIcon /> : <PlayIcon />}
          </button>
          <button type="button" className="icon-button" onClick={() => seekBy(-10)} aria-label="Back 10 seconds">
            <RewindIcon />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={toggleMute}
            aria-label={muted ? 'Unmute' : 'Mute'}
            aria-pressed={muted}
          >
            <VolumeIcon muted={muted} />
          </button>
          <span className="num time">
            {formatTime(time)} / {formatTime(duration)}
          </span>

          <span className="spacer" />

          {info.audio_tracks.length > 1 && (
            <label className="inline-field">
              Audio
              <select value={audioTrackId} onChange={(e) => chooseAudio(e.target.value)}>
                {info.audio_tracks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="inline-field">
            Subtitles
            <select value={subtitleLanguage} onChange={(e) => setSubtitleLanguage(e.target.value)}>
              <option value="off">Off</option>
              {info.subtitle_tracks.map((t) => (
                <option key={t.language} value={t.language}>
                  {languageLabel(t.language)}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={openFlag}>
            Flag this moment
          </button>
          <button type="button" className="icon-button" onClick={toggleFullScreen} aria-label="Full screen">
            <FullScreenIcon />
          </button>
        </div>

        <p className="meta num filter-summary">
          {activeFilters.length === 0
            ? 'No filters are active.'
            : info.runtime_removed > 0
              ? `${formatTime(info.runtime_removed)} will be skipped.`
              : `${activeFilters.length} moments filtered.`}
        </p>
        {error && (
          <p role="alert" className="error-note">
            {error}
          </p>
        )}
        {flagging && (
          <FlagMoment titleId={info.title_id} time={time} onClose={() => setFlagging(false)} />
        )}
      </div>
    </section>
  )
}
