'use client'

import { useRef, useState } from 'react'
import { api } from '@/api/client'
import type { ScriptLine } from '@/api/types'
import { ErrorNote } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { useAsync } from '@/hooks/useAsync'
import { formatTime } from '@/lib/format'

/** Line-by-line subtitle editor for one language, with SRT/VTT import and export. */
export function ScriptEditor({ titleId, language }: { titleId: string; language: string }) {
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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="secondary">
          <a href={api.subtitleDownloadUrl(titleId, language, 'srt', mask)}>Export SRT</a>
        </Button>
        <Button asChild variant="secondary">
          <a href={api.subtitleDownloadUrl(titleId, language, 'vtt', mask)}>Export VTT</a>
        </Button>
        <Button variant="secondary" onClick={() => fileInput.current?.click()}>
          Import your own file
        </Button>
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
      <label className="meta flex min-h-11 w-fit cursor-pointer items-center gap-3">
        <Checkbox checked={mask} onCheckedChange={(v) => setMask(v === true)} />
        Mask filtered words in exports (*****)
      </label>

      {notice && <p className="meta m-0">{notice}</p>}
      {error && <ErrorNote message={error} />}
      {script.error && <ErrorNote message={script.error} />}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] border-collapse text-[15px]">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="marquee-label w-[90px] px-3 py-2 font-bold">Time</th>
              <th className="marquee-label w-[40%] px-3 py-2 font-bold">Spoken</th>
              <th className="marquee-label px-3 py-2 font-bold">Subtitle</th>
            </tr>
          </thead>
          <tbody>
            {script.data?.map((line) => (
              <ScriptRow key={`${language}-${line.segment_id}`} line={line} titleId={titleId} language={language} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ScriptRow({ line, titleId, language }: { line: ScriptLine; titleId: string; language: string }) {
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
    <tr className="border-b border-line align-top">
      <td className="meta px-3 py-3 tabular-nums">{formatTime(line.start)}</td>
      <td className="px-3 py-3 text-ink-soft">{line.original}</td>
      <td className="px-3 py-2">
        <Textarea
          rows={2}
          value={text}
          aria-label={`Subtitle at ${formatTime(line.start)}`}
          className="min-h-0 resize-y"
          onChange={(e) => {
            setText(e.target.value)
            setState('idle')
          }}
          onBlur={() => void save()}
        />
        <span className="meta mt-1 block min-h-[22px]" aria-live="polite">
          {state === 'saving' && 'Saving…'}
          {state === 'saved' && 'Saved'}
          {state === 'error' && 'Could not save. Try again.'}
        </span>
      </td>
    </tr>
  )
}
