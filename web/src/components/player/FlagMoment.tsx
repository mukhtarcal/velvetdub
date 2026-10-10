import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type { CorrectionKind } from '../../api/types'
import { CATEGORY_ORDER, categoryLabel, formatTime } from '../../lib/format'

/** Tell the app it missed something, or filtered something it shouldn't have. */
export function FlagMoment({
  titleId,
  time,
  onClose,
}: {
  titleId: string
  time: number
  onClose: () => void
}) {
  const [kind, setKind] = useState<CorrectionKind>('missed')
  const [category, setCategory] = useState(CATEGORY_ORDER[0])
  const [note, setNote] = useState('')
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setState('saving')
    try {
      await api.addCorrection(titleId, {
        kind,
        at_seconds: time,
        category,
        note: note.trim() || null,
      })
      setState('saved')
    } catch {
      setState('error')
    }
  }

  return (
    <form className="flag-form" onSubmit={submit}>
      <fieldset>
        <legend>
          Flag the moment at <span className="num">{formatTime(time)}</span>
        </legend>
        <label>
          <input type="radio" name="kind" checked={kind === 'missed'} onChange={() => setKind('missed')} />{' '}
          Something should have been filtered here
        </label>
        <label>
          <input type="radio" name="kind" checked={kind === 'wrong'} onChange={() => setKind('wrong')} />{' '}
          This shouldn’t have been filtered
        </label>
      </fieldset>
      <label className="field">
        What kind
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORY_ORDER.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Note (optional)
        <input type="text" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="row-actions">
        <button type="submit" className="secondary" disabled={state === 'saving' || state === 'saved'}>
          Send
        </button>
        <button type="button" className="text" onClick={onClose}>
          {state === 'saved' ? 'Close' : 'Cancel'}
        </button>
        <span className="meta" aria-live="polite">
          {state === 'saved' && 'Thanks. Saved.'}
          {state === 'error' && 'Could not save that. Try again.'}
        </span>
      </div>
    </form>
  )
}
