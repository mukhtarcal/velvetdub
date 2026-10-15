import type { ExportState } from '../api/types'
import { formatBytes, formatDuration, formatTime } from './format'

/** One plain sentence on what the copy will be like with the cuts as they are now. */
export function copySummary(state: ExportState): string {
  if (state.output_seconds <= 0) return 'Everything is cut, so there is nothing left to save.'
  const parts: string[] = []
  if (state.cuts > 0) parts.push(`${state.cuts} ${state.cuts === 1 ? 'scene' : 'scenes'} cut`)
  if (state.muted_words > 0) {
    parts.push(`${state.muted_words} ${state.muted_words === 1 ? 'word' : 'words'} muted`)
  }
  const removed =
    state.removed_seconds > 0 ? `, ${formatDuration(state.removed_seconds)} shorter than the original` : ''
  const length = `Your copy will be ${formatTime(state.output_seconds)} long${removed}`
  return parts.length > 0 ? `${length}: ${parts.join(' and ')}.` : `${length}. Nothing is cut.`
}

export interface DownloadControl {
  /** `start` begins making the copy; `save` hands over the finished file. */
  action: 'start' | 'working' | 'save' | 'retry' | 'blocked'
  label: string
  hint: string
}

/** What the one main button on the download page does, and the line beside it. */
export function downloadControl(state: ExportState): DownloadControl {
  if (state.output_seconds <= 0) {
    return { action: 'blocked', label: 'Download the cleaned movie', hint: 'Leave something in first.' }
  }
  switch (state.status) {
    case 'working':
      return {
        action: 'working',
        label: 'Making your copy…',
        hint: `${state.percent}% done. You can leave this page; come back here to download it when it’s ready.`,
      }
    case 'ready':
      return {
        action: 'save',
        label: 'Download the cleaned movie',
        hint: `Your copy is ready${state.size_bytes ? ` (${formatBytes(state.size_bytes)})` : ''}. It matches the cuts above.`,
      }
    case 'failed':
      return { action: 'retry', label: 'Try again', hint: 'Nothing was saved, so this starts the copy again.' }
    default:
      return {
        action: 'start',
        label: 'Download the cleaned movie',
        hint: 'We make a new copy with these cuts, then it downloads. The original stays as it is. A full film takes a few minutes.',
      }
  }
}
