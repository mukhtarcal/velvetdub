import { useState } from 'react'

export interface SkipNoticeData {
  /** Ids of the detections inside the skipped region. */
  ids: string[]
  seconds: number
  label: string
  notes: string[]
}

/** “Skipped 42 s” in signal, then the category, then two text actions (docs/BRAND.md). */
export function SkipNotice({
  notice,
  onKeepIn,
}: {
  notice: SkipNoticeData
  onKeepIn: () => void
}) {
  const [explaining, setExplaining] = useState(false)

  return (
    <div className="skip-notice" role="status">
      <p className="skip-line">
        <span className="signal num">Skipped {notice.seconds} s</span> of {notice.label}
      </p>
      {explaining && (
        <p className="meta">{notice.notes.length > 0 ? notice.notes.join('. ') : 'No description was recorded.'}</p>
      )}
      <div className="skip-actions">
        <button type="button" className="text" onClick={() => setExplaining((v) => !v)}>
          What happened?
        </button>
        <button type="button" className="text" onClick={onKeepIn}>
          Keep it in
        </button>
      </div>
    </div>
  )
}
