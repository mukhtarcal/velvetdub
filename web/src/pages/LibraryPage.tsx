import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'
import { formatTime } from '../lib/format'
import { titleStatus } from '../lib/titles'

export function LibraryPage() {
  const { data: titles, error, loading } = useAsync(() => api.listTitles(), [])

  return (
    <>
      <PageHeader step="Library" title="Your titles">
        <Link to="/add" className="button primary">
          Add a title
        </Link>
      </PageHeader>

      {error && (
        <ErrorNote message="The server isn’t running. Start it with “uv run vd serve”, then reload." />
      )}
      {loading && !error && <p className="meta">Loading your titles…</p>}
      {titles?.length === 0 && <p>No titles yet. Add a title to get started.</p>}

      <ul className="title-list">
        {titles?.map((title) => {
          const status = titleStatus(title)
          return (
            <li key={title.id} className="title-row">
              <div>
                <div className="name">{title.name}</div>
                <div className="meta num">
                  {title.duration ? `${formatTime(title.duration)} · ` : ''}
                  {status.label}
                </div>
              </div>
              <div className="row-actions">
                {status.ready ? (
                  <>
                    <Link to={`/titles/${title.id}/review`} className="button secondary">
                      Review the cuts
                    </Link>
                    <Link to={`/titles/${title.id}/watch`} className="button primary">
                      Watch
                    </Link>
                  </>
                ) : (
                  <Link to={`/titles/${title.id}/process`} className="button secondary">
                    {status.label.startsWith('Stopped') ? 'Try again' : 'Process'}
                  </Link>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </>
  )
}
