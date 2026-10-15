import { TopBar } from '@/components/brand/TopBar'

/** Every page except the player: the velvet bar, then the page. */
export default function HouseLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <TopBar />
      <main className="mx-auto flex w-full max-w-[1184px] flex-col gap-10 px-4 pt-10 pb-20 sm:px-8 sm:pt-14">
        {children}
      </main>
      <div className="grain" aria-hidden="true" />
    </div>
  )
}
