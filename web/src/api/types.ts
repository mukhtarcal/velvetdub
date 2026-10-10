// Shapes returned by the API. Keep in sync with src/velvetdub/services/ and api/routers/.

export type FilterAction = 'mute' | 'replace' | 'blur' | 'skip' | 'summarize'

export interface Region {
  x: number
  y: number
  width: number
  height: number
}

export interface FilterItem {
  id: string
  category: string
  severity: string
  action: FilterAction
  start: number
  end: number
  text: string | null
  note: string | null
  confidence: number
  region: Region | null
}

export interface ReviewFilterItem extends FilterItem {
  kept: boolean
}

export interface AudioTrack {
  id: string
  label: string
  language: string | null
  kind: 'original' | 'dub'
  url: string
}

export interface SubtitleTrack {
  language: string
  url: string
}

export interface Profile {
  id: string
  name: string
}

export interface PlaybackInfo {
  title_id: string
  name: string
  duration: number | null
  source_url: string
  audio_tracks: AudioTrack[]
  subtitle_tracks: SubtitleTrack[]
  profile: Profile
  filters: FilterItem[]
  kept: string[]
  runtime_removed: number
}

export interface ReviewInfo {
  title_id: string
  name: string
  duration: number | null
  profile: Profile
  filters: ReviewFilterItem[]
  runtime_removed: number
}

export interface TitleSummary {
  id: string
  name: string
  created_at: string
  duration: number | null
  stages: Record<string, string>
}

export type StageProgress = 'pending' | 'running' | 'done' | 'skipped' | 'failed'

export interface JobState {
  title_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  stages: Record<string, StageProgress>
  error: string | null
}

export interface ScriptLine {
  segment_id: string
  start: number
  end: number
  speaker: string | null
  original: string
  text: string
}

export type CorrectionKind = 'missed' | 'wrong'

export interface CorrectionInput {
  kind: CorrectionKind
  at_seconds: number
  category?: string | null
  event_id?: string | null
  note?: string | null
}

/** Pipeline stages in order, with plain-language labels. */
export const PIPELINE_STAGES: { id: string; label: string }[] = [
  { id: 'extract_audio', label: 'Extracting the audio' },
  { id: 'transcribe', label: 'Transcribing the dialogue' },
  { id: 'visual_scan', label: 'Scanning the picture' },
  { id: 'translate', label: 'Translating' },
  { id: 'build_filters', label: 'Building the filter timeline' },
  { id: 'subtitles', label: 'Writing subtitles' },
]
