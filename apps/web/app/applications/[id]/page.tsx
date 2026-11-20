import { Suspense } from "react";

import ReviewView from "./review-view";

// The id is only known at request time; with cacheComponents, useParams must sit under Suspense.
export default function ReviewPage() {
  return (
    <Suspense fallback={<p className="text-sm text-zinc-500">Loading application…</p>}>
      <ReviewView />
    </Suspense>
  );
}
