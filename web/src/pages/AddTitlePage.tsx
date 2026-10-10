import { useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadTitle } from '../api/client'
import { LanguagePicker } from '../components/LanguagePicker'
import { ErrorNote, PageHeader } from '../components/PageHeader'

const ACCEPTED = '.mp4,.m4v,.mov,.mkv,.webm,.avi,video/*'

function nameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, '').replace(/[._]+/g, ' ').trim()
}

export function AddTitlePage() {
  const navigate = useNavigate()
  const abort = useRef<AbortController | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [languages, setLanguages] = useState<string[]>(['en'])
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const uploading = progress !== null

  function choose(chosen: File | null) {
    setFile(chosen)
    setError(null)
    if (chosen && !name) setName(nameFromFile(chosen))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || !name.trim()) return
    setError(null)
    setProgress(0)
    abort.current = new AbortController()
    try {
      const title = await uploadTitle(file, name.trim(), setProgress, abort.current.signal)
      navigate(`/titles/${title.id}/process`, { state: { autostart: languages } })
    } catch (e) {
      setProgress(null)
      setError(e instanceof Error ? e.message : 'The upload failed.')
    }
  }

  return (
    <>
      <PageHeader step="Add a title · step 1 of 2" title="Add a title" />
      <form className="stack" onSubmit={submit}>
        <div className="drop-zone">
          <p>{file ? file.name : 'Choose a movie or episode from your computer.'}</p>
          <label className="button secondary">
            {file ? 'Choose a different file' : 'Choose a file'}
            <input
              type="file"
              accept={ACCEPTED}
              hidden
              disabled={uploading}
              onChange={(e) => choose(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        <label className="field">
          Name
          <input
            type="text"
            value={name}
            maxLength={200}
            disabled={uploading}
            onChange={(e) => setName(e.target.value)}
          />
        </label>

        <div className="field">
          Subtitle languages
          <LanguagePicker value={languages} onChange={setLanguages} />
        </div>

        {error && <ErrorNote message={error} />}

        {uploading ? (
          <div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-label="Upload progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round((progress ?? 0) * 100)}
            >
              <div style={{ width: `${Math.round((progress ?? 0) * 100)}%` }} />
            </div>
            <p className="meta num">Uploading… {Math.round((progress ?? 0) * 100)}%</p>
            <button type="button" className="secondary" onClick={() => abort.current?.abort()}>
              Cancel
            </button>
          </div>
        ) : (
          <div>
            <button type="submit" className="primary" disabled={!file || !name.trim()}>
              Upload and continue
            </button>
          </div>
        )}
      </form>
    </>
  )
}
