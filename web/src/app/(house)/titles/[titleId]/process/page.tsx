import { ProcessView } from '@/components/views/ProcessView'

export default async function ProcessPage({ params }: { params: Promise<{ titleId: string }> }) {
  const { titleId } = await params
  return <ProcessView titleId={titleId} />
}
