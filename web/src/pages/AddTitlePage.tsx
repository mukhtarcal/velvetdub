import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, uploadTitle } from '../api/client'
import type { ScanCategory } from '../api/types'
import { FilterTiles } from '../components/FilterTiles'
import { LanguagePicker } from '../components/LanguagePicker'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { needsLanguage, processChoices, skipSummary, submitState, subtitleSummary } from '../lib/addTitle'
import { FILTERS } from '../lib/filters'
import { formatBytes, formatTime } from '../lib/format'
import { readRuntime } from '../lib/media'

const ACCEPTED = '.mp4,.m4v,.mov,.mkv,.webm,.avi,video/*'
const ALL_FILTER_IDS = FILTERS.map((f) => f.id)

function nameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, '').replace(/[._]+/g, ' ').trim()
}

export function AddTitlePage() {
  const navigate = useNavigate()
  const abort = useRef<AbortController | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [runtime, setRuntime] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [filters, setFilters] = useState<ScanCategory[]>([])
  const [subtitlesOn, setSubtitlesOn] = useState(false)
  const [languages, setLanguages] = useState<string[]>([])
  const [available, setAvailable] = useState<ScanCategory[]>(ALL_FILTER_IDS)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const uploading = progress !== null

  // Ask which filters the scanner can check. If the server can't say, offer all of them and let
  // the server refuse with a plain message.
  useEffect(() => {
    api.capabilities().then(
      (c) => {
        setAvailable(c.scan_categories)
        setFilters((chosen) => chosen.filter((id) => c.scan_categories.includes(id)))
      },
      () => undefined,
    )
  }, [])

  function choose(chosen: File | null) {
    setFile(chosen)
    setRuntime(null)
    setError(null)
    if (chosen && !name) setName(nameFromFile(chosen))
    if (chosen) void readRuntime(chosen).then(setRuntime)
  }

  const form = { hasFile: !!file, name, filters, subtitlesOn, languages }
  const { canSubmit, hint } = submitState(form)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || !canSubmit) return
    setError(null)
    setProgress(0)
    abort.current = new AbortController()
    try {
      const title = await uploadTitle(file, name.trim(), setProgress, abort.current.signal)
      navigate(`/titles/${title.id}/process`, { state: { autostart: processChoices(form) } })
    } catch (e) {
      setProgress(null)
      setError(e instanceof Error ? e.message : 'The upload failed.')
    }
  }

  return (
    <>
      <PageHeader step="Add a title · step 1 of 2" title="Add a title" />
      <form className="page-form" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
        <section className="section" aria-labelledby="film-h">
          <h2 id="film-h">The film</h2>
          <div className="upload-zone">
            <div className="what">
              {file ? (
                <>
                  <span>{file.name}</span>
                  <span className="meta num">
                    {formatBytes(file.size)}
                    {runtime ? ` · ${formatTime(runtime)}` : ''}
                  </span>
                </>
              ) : (
                <>
                  <span style={{ color: 'var(--ink-soft)' }}>Choose a movie or episode from your computer.</span>
                  <span className="meta">MP4, MOV, MKV, WebM or AVI.</span>
                </>
              )}
            </div>
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
              style={{ height: 48 }}
            />
          </label>
        </section>

        <section className="filter-panel" aria-labelledby="filters-h">
          <div className="section-head">
            <h2 id="filters-h">Filters</h2>
            <span className="meta">Optional</span>
          </div>
          <p style={{ margin: 0, maxWidth: 640 }}>
            Choose what to skip. We scan the picture for these and show you every cut before you watch. You can
            keep any of them in.
          </p>
          <FilterTiles value={filters} onChange={setFilters} available={available} disabled={uploading} />
          <p className="small" style={{ margin: 0 }}>
            Swearing in the dialogue is found from the words themselves, so it needs no scan. Once the video is done
            processing you can remove whatever swearing you choose.
          </p>
        </section>

        <section className="subtitle-box" aria-labelledby="subs-h">
          <div className="section-head">
            <h2 id="subs-h">Subtitles</h2>
            <span className="meta">Optional</span>
          </div>
          <div className="segmented" role="radiogroup" aria-label="Subtitles">
            <button
              type="button"
              role="radio"
              aria-checked={!subtitlesOn}
              disabled={uploading}
              onClick={() => setSubtitlesOn(false)}
            >
              No subtitles
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={subtitlesOn}
              disabled={uploading}
              onClick={() => setSubtitlesOn(true)}
            >
              Add subtitles
            </button>
          </div>
          {subtitlesOn && (
            <div className="stack" style={{ gap: 10 }}>
              <div className="meta">Languages</div>
              <LanguagePicker value={languages} onChange={setLanguages} disabled={uploading} />
              {needsLanguage(form) && (
                <div className="small" style={{ color: 'var(--ink-soft)' }}>
                  Choose at least one language, or pick No subtitles.
                </div>
              )}
            </div>
          )}
        </section>

        {error && <ErrorNote message={error} />}

        <div className="submit-bar">
          <dl className="summary">
            <dt>Skip</dt>
            <dd>{skipSummary(filters)}</dd>
            <dt>Subtitles</dt>
            <dd>{subtitleSummary(form)}</dd>
          </dl>
          {uploading ? (
            <div className="stack" style={{ gap: 12 }}>
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
              <div className="row-actions">
                <span className="meta num">Uploading… {Math.round((progress ?? 0) * 100)}%</span>
                <button type="button" className="secondary" onClick={() => abort.current?.abort()}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="row-actions" style={{ gap: '16px 24px' }}>
              <button type="submit" className="primary" disabled={!canSubmit} style={{ minHeight: 48, padding: '0 28px' }}>
                Upload and continue
              </button>
              <span className="meta">{hint}</span>
            </div>
          )}
        </div>
      </form>
    </>
  )
}
