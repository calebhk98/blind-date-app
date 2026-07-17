import { ReviewProfileClient } from "./ReviewProfileClient";

interface ReviewProfileDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ReviewProfileDetailPage({
  params,
}: ReviewProfileDetailPageProps) {
  const { id } = await params;
  return <ReviewProfileClient profileId={id} />;
}
