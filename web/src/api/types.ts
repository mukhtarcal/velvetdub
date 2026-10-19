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
  /** Whether the dialogue was checked for swearing. Absent or null for an older title: it was. */
  swearing_checked?: boolean | null
}

/** The four things the picture scan can be asked to look for. */
export type ScanCategory = 'nudity' | 'sexual_content' | 'scary_scenes' | 'violence'

/** Everything that can be chosen under Filters: the four scanned in the picture, and swearing,
 * which is found from the words in the dialogue. Only what is chosen is processed. */
export type FilterChoice = ScanCategory | 'swearing'

/** What was asked for the last time processing started. */
export interface Choices {
  filter_categories: string[]
  subtitle_languages: string[]
  /** Languages a dub was asked for. Older titles may not list it. */
  dub_languages?: string[]
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
  filter_categories: FilterChoice[]
  dub_languages: string[]
}

export interface Capabilities {
  scan_categories: ScanCategory[]
  /** Languages a dub can be made in; empty when this install can't dub yet. */
  dub_languages: string[]
}

export type StageProgress = 'pending' | 'running' | 'done' | 'skipped' | 'failed'

export interface JobState {
  title_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  stages: Record<string, StageProgress>
  error: string | null
}

export type ExportStatus = 'none' | 'working' | 'ready' | 'failed'

/** The cleaned copy of a film. The numbers describe the copy the cuts as they are now would make. */
export interface ExportState {
  status: ExportStatus
  percent: number
  error: string | null
  filename: string
  size_bytes: number | null
  output_seconds: number
  removed_seconds: number
  cuts: number
  muted_words: number
}

export interface ScriptLine {
  segment_id: string
  start: number
  end: number
  speaker: string | null
  original: string
  text: string
}

export interface StageInfo {
  id: string
  label: string
}

/** Pipeline stages in order, with plain-language labels. */
export const PIPELINE_STAGES: StageInfo[] = [
  { id: 'extract_audio', label: 'Extracting the audio' },
  { id: 'transcribe', label: 'Transcribing the dialogue' },
  { id: 'visual_scan', label: 'Scanning the picture' },
  { id: 'translate', label: 'Translating' },
  { id: 'build_filters', label: 'Building the filter timeline' },
  { id: 'subtitles', label: 'Writing subtitles' },
]

/** The extra steps of a dub. They are listed only for a title that was asked to be dubbed: for
 * every other title they do nothing, and showing them would only add noise. */
export const DUBBING_STAGES: StageInfo[] = [
  { id: 'separate', label: 'Separating voices from the music' },
  { id: 'dub_transcribe', label: 'Listening to the voices alone' },
  { id: 'dub_translate', label: 'Writing the dub script' },
  { id: 'dub_voices', label: 'Copying each speaker’s voice' },
  { id: 'dub_speech', label: 'Recording the dub' },
  { id: 'dub_mix', label: 'Mixing the dub into the film' },
]

export function stagesFor(dubbing: boolean): StageInfo[] {
  return dubbing ? [...PIPELINE_STAGES, ...DUBBING_STAGES] : PIPELINE_STAGES
}
