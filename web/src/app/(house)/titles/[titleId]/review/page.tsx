import { ReviewView } from '@/components/views/ReviewView'

export default async function ReviewPage({ params }: { params: Promise<{ titleId: string }> }) {
  const { titleId } = await params
  return <ReviewView titleId={titleId} />
}
