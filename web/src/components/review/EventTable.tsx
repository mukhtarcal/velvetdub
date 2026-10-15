import type { ReviewFilterItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { categoryLabel, formatTime } from '@/lib/format'
import { cn } from '@/lib/utils'

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
    <Table className="text-[15px]">
      <TableHeader>
        <TableRow className="border-line hover:bg-transparent">
          <TableHead className="marquee-label h-10 w-[120px] px-3">Time</TableHead>
          <TableHead className="marquee-label h-10 px-3">What</TableHead>
          <TableHead className="marquee-label h-10 px-3">What happens</TableHead>
          <TableHead className="h-10 px-3" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {filters.map((f) => (
          <TableRow
            key={f.id}
            data-kept={f.kept}
            data-category={f.category}
            className="border-line transition-colors hover:bg-panel/70"
          >
            <TableCell className="px-3 py-2 text-ink tabular-nums">
              <span className="flex items-center gap-2.5">
                <span className="h-4 w-[3px] shrink-0 bg-[var(--cat)]" aria-hidden="true" />
                {formatTime(f.start)}
                {f.end - f.start >= 1 ? `–${formatTime(f.end)}` : ''}
              </span>
            </TableCell>
            <TableCell className="px-3 py-2 whitespace-normal text-ink-soft">{describe(f)}</TableCell>
            <TableCell className={cn('px-3 py-2', f.kept ? 'text-muted-foreground' : 'text-ink')}>
              {f.kept ? 'Kept in' : (ACTION_WORD[f.action] ?? f.action)}
            </TableCell>
            <TableCell className="px-3 py-1 text-right">
              <Button variant="text" onClick={() => onToggle(f)}>
                {f.kept ? 'Filter again' : 'Keep it in'}
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
