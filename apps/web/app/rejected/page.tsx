import { ApplicationList } from "@/components/application-list";

export default function Page() {
  return <ApplicationList title="Rejected" status="rejected" empty="No rejected applications yet." />;
}
