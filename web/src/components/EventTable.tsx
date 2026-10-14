import type { ReviewFilterItem } from '../api/types'
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

/** Every moment that will be cut, each with its own "Keep it in" / "Filter again". */
export function EventTable({
  filters,
  onToggle,
}: {
  filters: ReviewFilterItem[]
  onToggle: (f: ReviewFilterItem) => void
}) {
  return (
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
              <button type="button" className="text" onClick={() => onToggle(f)}>
                {f.kept ? 'Filter again' : 'Keep it in'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
