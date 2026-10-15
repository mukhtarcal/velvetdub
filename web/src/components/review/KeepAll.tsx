import type { ReviewFilterItem } from '@/api/types'
import { Button } from '@/components/ui/button'

/** "Leave all in" for a group of moments (a whole category, or every moderate word), and the
 * way back once they are all left in. */
export function KeepAll({
  items,
  label,
  onSetKept,
}: {
  items: ReviewFilterItem[]
  /** What the group is, for screen readers: "mild swearing". */
  label: string
  onSetKept: (ids: string[], keep: boolean) => void
}) {
  if (items.length === 0) return null
  const allKept = items.every((f) => f.kept)
  // Only change what is not already in that state, so one click never undoes a single choice.
  const targets = items.filter((f) => f.kept === allKept).map((f) => f.id)
  return (
    <Button
      variant="secondary"
      aria-label={`${allKept ? 'Filter again' : 'Leave in'} all ${label}`}
      onClick={() => onSetKept(targets, !allKept)}
    >
      {allKept ? 'Filter all again' : 'Leave all in'}
    </Button>
  )
}
