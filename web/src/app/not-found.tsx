import Link from 'next/link'
import { TopBar } from '@/components/brand/TopBar'

export default function NotFound() {
  return (
    <div className="flex min-h-svh flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-[1184px] px-4 pt-14 sm:px-8">
        <p>
          That page doesn’t exist. Go back to the{' '}
          <Link href="/library" className="text-action">
            library
          </Link>
          .
        </p>
      </main>
    </div>
  )
}
