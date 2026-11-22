import { ApplicationList } from "@/components/application-list";

export default function Page() {
  return <ApplicationList title="Approved" status="approved" empty="No approved applications yet." />;
}
