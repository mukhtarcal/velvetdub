import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ReviewFilterItem } from '../api/types'
import { FilterTimeline } from '../components/FilterTimeline'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { ScriptEditor } from '../components/ScriptEditor'
import { useAsync } from '../hooks/useAsync'
import { useSelectedProfile } from '../hooks/useSelectedProfile'
import { categoryLabel, formatTime } from '../lib/format'

const ACTION_WORD: Record<string, string> = {
  skip: 'Skipped',
  mute: 'Muted',
  replace: 'Replaced',
  blur: 'Blurred',
  summarize: 'Summarized',
}

function describe(f: ReviewFilterItem): string {
  const what = f.text ? `“${f.text}”` : (f.note ?? '')
  return `${categoryLabel(f.category)} (${f.severity})${what ? ` · ${what}` : ''}`
}

export function ReviewPage() {
  const { titleId = '' } = useParams()
  const [profileId, setProfileId] = useSelectedProfile()
  const profiles = useAsync(() => api.listProfiles(), [])
  const review = useAsync(() => api.review(titleId, profileId), [titleId, profileId])
  const playback = useAsync(() => api.playback(titleId, profileId), [titleId, profileId])
  const [error, setError] = useState<string | null>(null)

  async function toggle(f: ReviewFilterItem) {
    setError(null)
    try {
      await (f.kept ? api.filterEvent(titleId, f.id) : api.keepEvent(titleId, f.id))
      review.reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update that moment.')
    }
  }

  const info = review.data
  const filters = info?.filters ?? []
  const active = filters.filter((f) => !f.kept)
  const skips = active.filter((f) => f.action === 'skip').length
  const mutes = active.filter((f) => f.action === 'mute' || f.action === 'replace').length
  const languages = playback.data?.subtitle_tracks.map((t) => t.language) ?? []

  return (
    <>
      <PageHeader step="Before the curtain goes up" title={info?.name ?? 'Review the cuts'}>
        <div className="row-actions">
          <label className="field">
            Filter profile
            <select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
              {(profiles.data ?? [{ id: 'family', name: 'Family (PG)' }]).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <Link to={`/titles/${titleId}/watch`} className="button primary">
            Watch
          </Link>
        </div>
      </PageHeader>

      {review.error && <ErrorNote message={review.error} />}
      {error && <ErrorNote message={error} />}

      {info && (
        <>
          <p className="num">
            {info.runtime_removed > 0 ? `Removes ${formatTime(info.runtime_removed)}` : 'Removes nothing'}
            {info.duration ? ` of ${formatTime(info.duration)}` : ''} · {skips} {skips === 1 ? 'scene' : 'scenes'}{' '}
            skipped · {mutes} {mutes === 1 ? 'word' : 'words'} muted
          </p>

          <section className="panel" aria-labelledby="filters-heading">
            <h2 id="filters-heading" className="signal-heading">
              Filters
            </h2>
            {info.duration ? (
              <FilterTimeline filters={filters} duration={info.duration} />
            ) : (
              <p className="meta">The film’s length isn’t known yet, so the timeline can’t be drawn.</p>
            )}

            {filters.length > 0 && (
              <table className="events">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>What</th>
                    <th>What happens</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {filters.map((f) => (
                    <tr key={f.id} data-kept={f.kept}>
                      <td className="num">
                        {formatTime(f.start)}
                        {f.end - f.start >= 1 ? `–${formatTime(f.end)}` : ''}
                      </td>
                      <td>{describe(f)}</td>
                      <td>{f.kept ? 'Kept in' : (ACTION_WORD[f.action] ?? f.action)}</td>
                      <td>
                        <button type="button" className="text" onClick={() => void toggle(f)}>
                          {f.kept ? 'Filter again' : 'Keep it in'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="panel" aria-labelledby="script-heading">
            <h2 id="script-heading">Subtitles</h2>
            {languages.length > 0 ? (
              <ScriptEditor titleId={titleId} languages={languages} profileId={profileId} />
            ) : (
              <p className="meta">No subtitles have been written for this title yet.</p>
            )}
          </section>
        </>
      )}
    </>
  )
}
