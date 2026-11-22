"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, ErrorBox, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

export default function Home() {
  return (
    <div className="mx-auto max-w-xl">
      <UploadForm />
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
    <Card title="Create application">
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
