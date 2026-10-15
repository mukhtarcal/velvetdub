import { DownloadView } from '@/components/views/DownloadView'

export default async function DownloadPage({ params }: { params: Promise<{ titleId: string }> }) {
  const { titleId } = await params
  return <DownloadView titleId={titleId} />
}
