import { ApplicationList } from "@/components/application-list";

export default function Page() {
  return <ApplicationList title="In review" status="in_review,processing,failed" empty="Nothing waiting for review." />;
}
