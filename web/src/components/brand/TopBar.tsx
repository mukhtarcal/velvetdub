'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Mark } from './Mark'

// Only pages that exist are listed. Settings arrives in a later step (1.5).
const NAV = [
  { href: '/', label: 'Add a title', exact: true },
  { href: '/library', label: 'Library', exact: false },
]

/** A slim velvet bar across the top: wordmark on the left, nav on the right, the current page on
 * a velvet-shadow inset, a gilt double rule along the lower edge. */
export function TopBar() {
  const pathname = usePathname() ?? '/'
  return (
    <header className="velvet-bar sticky top-0 z-40">
      <div className="mx-auto flex min-h-[72px] max-w-[1184px] flex-wrap items-center justify-between gap-x-8 gap-y-2 px-4 sm:px-8">
        <Link href="/" className="flex items-center gap-3 py-3 text-ink no-underline">
          <Mark />
          <span className="font-display text-[26px] leading-none sm:text-[30px]">Velvet Dub</span>
        </Link>
        <nav aria-label="Main" className="flex gap-1">
          {NAV.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'relative flex min-h-11 items-center px-4 text-on-velvet no-underline transition-colors duration-200 hover:text-ink sm:px-[18px]',
                  active && 'bg-velvet-shadow text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-gilt',
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
