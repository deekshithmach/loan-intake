"use client";
import Link from "next/link";

import { Card, ErrorBox, Spinner, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { when } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

export function ApplicationList({ title, status, empty }: { title: string; status: string; empty: string }) {
  const { data, error, refresh } = usePolling(() => api.list(status), 3000, (apps) => apps.some((a) => a.status === "processing"));

  return (
    <Card title={title} right={<button onClick={refresh} className="text-xs text-zinc-500 hover:text-zinc-900">Refresh</button>}>
      {error && <ErrorBox message={error} onRetry={refresh} />}
      {!data && !error && (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-500"><Spinner /> Loading…</div>
      )}
      {data?.length === 0 && <p className="py-8 text-center text-sm text-zinc-500">{empty}</p>}
      {!!data?.length && (
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr className="border-b border-zinc-100">
                <th className="px-4 py-2 font-medium">Application</th>
                <th className="px-4 py-2 font-medium">Applicant</th>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">Flags</th>
                <th className="px-4 py-2 text-right font-medium">Received</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                  <td className="px-4 py-2 font-mono text-xs">
                    <Link href={`/applications/${a.id}`} className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-800" title="Open application">{a.id}</Link>
                  </td>
                  <td className="px-4 py-2">{a.applicant_name ?? <span className="text-zinc-400">—</span>}</td>
                  <td className="px-4 py-2 font-mono text-xs text-zinc-600">{a.model ?? <span className="text-zinc-400">—</span>}</td>
                  <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
                  <td className={`px-4 py-2 text-right tabular-nums ${a.flag_count ? "font-semibold text-rose-700" : "text-zinc-400"}`}>{a.flag_count}</td>
                  <td className="px-4 py-2 text-right text-zinc-500">{when(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
