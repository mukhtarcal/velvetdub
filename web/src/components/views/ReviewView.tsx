'use client'

import Link from 'next/link'
import { api } from '@/api/client'
import { ErrorNote, PageHeader } from '@/components/PageHeader'
import { CutsReview } from '@/components/review/CutsReview'
import { Panel } from '@/components/review/Panel'
import { ScriptEditor } from '@/components/review/ScriptEditor'
import { Tabs } from '@/components/review/Tabs'
import { Button } from '@/components/ui/button'
import { useAsync } from '@/hooks/useAsync'
import { useCuts } from '@/hooks/useCuts'
import { languageLabel } from '@/lib/titles'

/** "Before the curtain goes up": every cut, with "Keep it in", plus the subtitle editor. */
export function ReviewView({ titleId }: { titleId: string }) {
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
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild variant="secondary" className="min-h-12">
              <Link href={`/titles/${titleId}/download`}>Download</Link>
            </Button>
            <Button asChild variant="primary">
              <Link href={`/titles/${titleId}/watch`}>Watch</Link>
            </Button>
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
                <Panel id="translation-heading" title="Translation">
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
                    <p className="meta m-0">No subtitles have been written for this title yet.</p>
                  )}
                </Panel>
              ),
            },
          ]}
        />
      )}
    </>
  )
}
