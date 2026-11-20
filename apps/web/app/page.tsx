"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, ErrorBox, Spinner, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { when } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

export default function Home() {
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <UploadForm />
      <ApplicationList />
    </div>
  );
}

function UploadForm() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const add = (list: FileList | null) => {
    const pdfs = Array.from(list ?? []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (list && pdfs.length < list.length) setError("Only PDF files are accepted.");
    else setError(null);
    setFiles((prev) => [...prev, ...pdfs.filter((p) => !prev.some((f) => f.name === p.name))].slice(0, 10));
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const { id } = await api.upload(files);
      router.push(`/applications/${id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Card title="New application">
      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files); }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center text-sm transition ${
          dragging ? "border-zinc-900 bg-zinc-100" : "border-zinc-300 hover:border-zinc-400"
        }`}
      >
        <span className="font-medium">Drop PDFs here or click to browse</span>
        <span className="mt-1 text-xs text-zinc-500">Pay stub, W-2 and bank statement</span>
        <input type="file" accept="application/pdf,.pdf" multiple className="sr-only" onChange={(e) => add(e.target.files)} />
      </label>

      {files.length > 0 && (
        <ul className="mt-3 divide-y divide-zinc-100 rounded-lg border border-zinc-200 text-sm">
          {files.map((f) => (
            <li key={f.name} className="flex items-center justify-between px-3 py-1.5">
              <span className="truncate">{f.name}</span>
              <button onClick={() => setFiles(files.filter((x) => x !== f))} className="text-xs text-zinc-500 hover:text-rose-600" aria-label={`Remove ${f.name}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <div className="mt-3"><ErrorBox message={error} /></div>}

      <button
        onClick={submit}
        disabled={!files.length || busy}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy && <Spinner />}
        {busy ? "Uploading…" : `Submit ${files.length || ""} document${files.length === 1 ? "" : "s"}`}
      </button>
    </Card>
  );
}

function ApplicationList() {
  const { data, error, refresh } = usePolling(api.list, 3000, (apps) => apps.some((a) => a.status === "processing"));

  return (
    <Card title="Applications" right={<button onClick={refresh} className="text-xs text-zinc-500 hover:text-zinc-900">Refresh</button>}>
      {error && <ErrorBox message={error} onRetry={refresh} />}
      {!data && !error && (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-500"><Spinner /> Loading…</div>
      )}
      {data?.length === 0 && <p className="py-8 text-center text-sm text-zinc-500">No applications yet. Upload documents to start.</p>}
      {!!data?.length && (
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr className="border-b border-zinc-100">
                <th className="px-4 py-2 font-medium">Application</th>
                <th className="px-4 py-2 font-medium">Applicant</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">Flags</th>
                <th className="px-4 py-2 text-right font-medium">Received</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                  <td className="px-4 py-2 font-mono text-xs">
                    <Link href={`/applications/${a.id}`} className="underline-offset-2 hover:underline">{a.id}</Link>
                  </td>
                  <td className="px-4 py-2">{a.applicant_name ?? <span className="text-zinc-400">—</span>}</td>
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
