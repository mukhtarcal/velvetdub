import { useRef, useState } from 'react'
import { api } from '../api/client'
import type { ScriptLine } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { formatTime } from '../lib/format'
import { ErrorNote } from './PageHeader'

/** Line-by-line subtitle editor for one language, with SRT/VTT import and export. */
export function ScriptEditor({
  titleId,
  language,
}: {
  titleId: string
  language: string
}) {
  const script = useAsync(() => api.script(titleId, language), [titleId, language])
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mask, setMask] = useState(true)
  const fileInput = useRef<HTMLInputElement>(null)

  async function importFile(file: File) {
    setError(null)
    setNotice(null)
    try {
      const { lines } = await api.importSubtitles(titleId, language, await file.text())
      setNotice(`Imported ${lines} lines from ${file.name}.`)
      script.reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not import that file.')
    }
  }

  return (
    <div className="stack">
      <div className="row-actions">
        <a
          className="button secondary"
          href={api.subtitleDownloadUrl(titleId, language, 'srt', mask)}
        >
          Export SRT
        </a>
        <a
          className="button secondary"
          href={api.subtitleDownloadUrl(titleId, language, 'vtt', mask)}
        >
          Export VTT
        </a>
        <button type="button" className="secondary" onClick={() => fileInput.current?.click()}>
          Import your own file
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".srt,.vtt,text/vtt"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void importFile(file)
            e.target.value = ''
          }}
        />
      </div>
      <label className="meta">
        <input type="checkbox" checked={mask} onChange={(e) => setMask(e.target.checked)} /> Mask
        filtered words in exports (*****)
      </label>

      {notice && <p className="meta">{notice}</p>}
      {error && <ErrorNote message={error} />}
      {script.error && <ErrorNote message={script.error} />}

      <table className="script">
        <thead>
          <tr>
            <th>Time</th>
            <th>Spoken</th>
            <th>Subtitle</th>
          </tr>
        </thead>
        <tbody>
          {script.data?.map((line) => (
            <ScriptRow key={`${language}-${line.segment_id}`} line={line} titleId={titleId} language={language} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ScriptRow({
  line,
  titleId,
  language,
}: {
  line: ScriptLine
  titleId: string
  language: string
}) {
  const [text, setText] = useState(line.text)
  const [saved, setSaved] = useState(line.text)
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  async function save() {
    const trimmed = text.trim()
    if (!trimmed || trimmed === saved) {
      setText(trimmed || saved)
      return
    }
    setState('saving')
    try {
      await api.editLine(titleId, language, line.segment_id, trimmed)
      setSaved(trimmed)
      setState('saved')
    } catch {
      setState('error')
    }
  }

  return (
    <tr>
      <td className="num meta">{formatTime(line.start)}</td>
      <td>{line.original}</td>
      <td>
        <textarea
          rows={2}
          value={text}
          aria-label={`Subtitle at ${formatTime(line.start)}`}
          onChange={(e) => {
            setText(e.target.value)
            setState('idle')
          }}
          onBlur={() => void save()}
        />
        <span className="meta" aria-live="polite">
          {state === 'saving' && 'Saving…'}
          {state === 'saved' && 'Saved'}
          {state === 'error' && 'Could not save. Try again.'}
        </span>
      </td>
    </tr>
  )
}
