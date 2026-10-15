import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { CutsReview } from '../components/CutsReview'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { ScriptEditor } from '../components/ScriptEditor'
import { useAsync } from '../hooks/useAsync'
import { useCuts } from '../hooks/useCuts'
import { languageLabel } from '../lib/titles'
import { Tabs } from '../components/Tabs'

export function ReviewPage() {
  const { titleId = '' } = useParams()
  const { review, error, errorRef, setKept, toggle } = useCuts(titleId)
  const playback = useAsync(() => api.playback(titleId), [titleId])

  const info = review.data
  const languages = playback.data?.subtitle_tracks.map((t) => t.language) ?? []

  return (
    <>
      <PageHeader
        step="Before the curtain goes up"
        title={info?.name ?? 'Review the cuts'}
        action={
          <div className="row-actions">
            <Link to={`/titles/${titleId}/download`} className="button secondary" style={{ minHeight: 48 }}>
              Download
            </Link>
            <Link to={`/titles/${titleId}/watch`} className="button primary" style={{ minHeight: 48, padding: '0 28px' }}>
              Watch
            </Link>
          </div>
        }
      />

      {review.error && <ErrorNote message={review.error} />}
      {error && (
        <div ref={errorRef}>
          <ErrorNote message={error} />
        </div>
      )}

      {info && (
        <CutsReview
          info={info}
          onToggle={toggle}
          onSetKept={setKept}
          extraTabs={[
            {
              id: 'translation',
              label: 'Translation',
              count: languages.length,
              content: (
                <section className="panel" aria-labelledby="translation-heading">
                  <h2 id="translation-heading">Translation</h2>
                  {languages.length > 0 ? (
                    <Tabs
                      level="inner"
                      label="Language"
                      tabs={languages.map((code) => ({
                        id: code,
                        label: languageLabel(code),
                        content: <ScriptEditor titleId={titleId} language={code} />,
                      }))}
                    />
                  ) : (
                    <p className="meta">No subtitles have been written for this title yet.</p>
                  )}
                </section>
              ),
            },
          ]}
        />
      )}
    </>
  )
}
