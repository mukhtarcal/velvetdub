import { WatchView } from '@/components/views/WatchView'

/** The player is full-screen, without the top bar. */
export default async function WatchPage({ params }: { params: Promise<{ titleId: string }> }) {
  const { titleId } = await params
  return <WatchView titleId={titleId} />
}
