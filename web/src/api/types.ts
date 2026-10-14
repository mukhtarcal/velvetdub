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

export interface PlaybackInfo {
  title_id: string
  name: string
  duration: number | null
  source_url: string
  audio_tracks: AudioTrack[]
  subtitle_tracks: SubtitleTrack[]
  filters: FilterItem[]
  kept: string[]
  runtime_removed: number
}

export interface ReviewInfo {
  title_id: string
  name: string
  duration: number | null
  filters: ReviewFilterItem[]
  runtime_removed: number
  scanned_categories: string[] | null
}

/** The four things the picture scan can be asked to look for (swearing needs no scan). */
export type ScanCategory = 'nudity' | 'sexual_content' | 'scary_scenes' | 'violence'

/** What was asked for the last time processing started. */
export interface Choices {
  filter_categories: string[]
  subtitle_languages: string[]
}

export interface TitleSummary {
  id: string
  name: string
  created_at: string
  duration: number | null
  stages: Record<string, string>
  choices: Choices | null
  /** What the picture scan actually looked for; null until it has run. */
  scanned_categories: string[] | null
}

export interface ProcessChoices {
  subtitle_languages: string[]
  filter_categories: ScanCategory[]
}

export interface Capabilities {
  scan_categories: ScanCategory[]
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
