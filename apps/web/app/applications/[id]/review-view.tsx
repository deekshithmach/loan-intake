"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AuditTrail, DocFields, FlagsPanel, type Edits } from "@/components/review";
import { Card, ErrorBox, Spinner, StatusBadge } from "@/components/ui";
import { api, type AppDetail, type AuditEvent, type Evidence } from "@/lib/api";
import { DOC_LABELS, DOC_ORDER, INT_FIELDS, usd } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

const stillWorking = (a: AppDetail) => a.status === "processing" || (a.status === "in_review" && !a.awaiting_review);

export default function ReviewView() {
  const { id } = useParams<{ id: string }>();
  const { data: app, error, refresh, setData } = usePolling(() => api.get(id), 2000, stillWorking);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    api.audit(id).then(setAudit).catch(() => setAudit([]));
  }, [id, app?.status]);

  if (error && !app) return <ErrorBox message={error} onRetry={refresh} />;
  if (!app) return <div className="flex items-center gap-2 text-sm text-zinc-500"><Spinner /> Loading application…</div>;

  return (
    <div className="space-y-4">
      <Header app={app} />
      {error && <ErrorBox message={error} onRetry={refresh} />}
      {stillWorking(app) ? (
        <Processing />
      ) : app.status === "failed" ? (
        <>
          <ErrorBox message="Processing failed. See the audit trail for details, then re-upload the documents." />
          <AuditTrail events={audit} />
        </>
      ) : (
        <Workspace key={app.status} app={app} audit={audit}
          onDone={(a) => { setData(a); api.audit(id).then(setAudit).catch(() => {}); }} />
      )}
    </div>
  );
}

function Header({ app }: { app: AppDetail }) {
  const ex = Object.values(app.extractions ?? {});
  const cost = ex.reduce((s, e) => s + e.usage.cost_usd, 0);
  const secs = ex.reduce((s, e) => s + e.usage.latency_ms, 0) / 1000;
  const tokens = ex.reduce((s, e) => s + e.usage.input_tokens + e.usage.output_tokens, 0);
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-900">← All applications</Link>
        <h1 className="mt-1 flex items-center gap-3 text-xl font-semibold">
          {app.applicant_name ?? "New application"}
          <StatusBadge status={app.status} />
        </h1>
        <p className="font-mono text-xs text-zinc-500">{app.id}</p>
      </div>
      {ex.length > 0 && (
        <p className="text-xs text-zinc-500">AI processing: {tokens.toLocaleString()} tokens · ${cost.toFixed(4)} · {secs.toFixed(1)}s</p>
      )}
    </div>
  );
}

function Processing() {
  return (
    <Card title="Processing">
      <div className="flex items-center gap-3 py-6 text-sm text-zinc-600">
        <Spinner className="h-5 w-5" />
        <div>
          <p className="font-medium text-zinc-900">Reading documents…</p>
          <p>Classifying, extracting fields and cross-checking. This usually takes 15–40 seconds; the page updates automatically.</p>
        </div>
      </div>
    </Card>
  );
}

function Workspace({ app, audit, onDone }: { app: AppDetail; audit: AuditEvent[] | null; onDone: (a: AppDetail) => void }) {
  const editable = app.awaiting_review;
  const docs = DOC_ORDER.filter((d) => app.extractions[d]).concat(Object.keys(app.extractions).filter((d) => !DOC_ORDER.includes(d)));
  const [doc, setDoc] = useState(docs[0] ?? "paystub");
  const [focus, setFocus] = useState<Evidence | null>(null);
  const [edits, setEdits] = useState<Edits>({});
  const [decisions, setDecisions] = useState<Record<string, "accept" | "dismiss">>({});
  const [reviewer, setReviewer] = useState(() => {
    try { return localStorage.getItem("reviewer") ?? ""; } catch { return ""; }
  });
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const ex = app.extractions[doc];
  const editCount = Object.values(edits).reduce((n, f) => n + Object.keys(f).length, 0);

  const setEdit = (d: string, field: string, value: string, original: string) =>
    setEdits((prev) => {
      const next = { ...prev, [d]: { ...prev[d] } };
      if (value === original) delete next[d][field]; else next[d][field] = value;
      if (!Object.keys(next[d]).length) delete next[d];
      return next;
    });

  const submit = async (decision: "approve" | "reject") => {
    if (!reviewer.trim()) { setSubmitError("Enter your name before submitting."); return; }
    try { localStorage.setItem("reviewer", reviewer.trim()); } catch {}
    setSubmitting(decision);
    setSubmitError(null);
    const payload = Object.fromEntries(Object.entries(edits).map(([d, fields]) => [d,
      Object.fromEntries(Object.entries(fields).map(([f, v]) => [f, INT_FIELDS.has(f) ? Number(v) : v]))]));
    try {
      onDone(await api.review(app.id, { decision, reviewer: reviewer.trim(), edits: payload, flag_decisions: decisions, notes }));
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(null);
    }
  };

  const profile = app.profile as { open_flags?: number; reviewer?: string; notes?: string; verified_income?: { annual_w2_cents?: number } } | null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Left: the source document */}
      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <div className="flex gap-1" role="tablist">
          {docs.map((d) => (
            <button key={d} role="tab" aria-selected={d === doc} onClick={() => { setDoc(d); setFocus(null); }}
              className={`rounded-md px-3 py-1.5 text-sm ${d === doc ? "bg-zinc-900 text-white" : "bg-white text-zinc-700 hover:bg-zinc-100"}`}>
              {DOC_LABELS[d] ?? d}
              {!app.extractions[d].ok && <span className="ml-1 text-rose-400">!</span>}
            </button>
          ))}
        </div>
        {ex && (
          <a href={api.fileUrl(app.id, ex.file)} target="_blank" rel="noreferrer" className="block text-right text-xs text-zinc-500 underline-offset-2 hover:underline">
            Open PDF in new tab ↗
          </a>
        )}
        {ex ? (
          <iframe key={ex.file} src={api.fileUrl(app.id, ex.file)} title={`${DOC_LABELS[doc]} PDF`}
            className="h-[75vh] w-full rounded-xl border border-zinc-200 bg-white" />
        ) : <p className="text-sm text-zinc-500">No document.</p>}
      </div>

      {/* Right: flags, fields, decision */}
      <div className="space-y-4">
        {!editable && (
          <div className={`rounded-xl border p-4 text-sm ${app.status === "approved" ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50"}`}>
            <p className="font-semibold">{app.status === "approved" ? "Approved" : "Rejected"} by {profile?.reviewer}</p>
            {profile?.notes && <p className="mt-1">“{profile.notes}”</p>}
            <p className="mt-1 text-zinc-600">
              W-2 income {usd(profile?.verified_income?.annual_w2_cents)} · {profile?.open_flags ?? 0} confirmed flag(s)
            </p>
          </div>
        )}

        <FlagsPanel flags={app.flags} editable={editable} decisions={decisions}
          setDecision={(c, d) => setDecisions((p) => ({ ...p, [c]: d }))}
          onEvidence={(e) => { setDoc(e.doc); setFocus({ ...e }); }} />

        <Card title={`Extracted fields · ${DOC_LABELS[doc] ?? doc}`}>
          <DocFields docKey={doc} ex={ex} editable={editable} edits={edits} setEdit={setEdit} focus={focus} />
        </Card>

        {editable && (
          <Card title="Decision">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="text-xs text-zinc-500">Reviewer</span>
                <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name"
                  className="mt-0.5 w-full rounded-md border border-zinc-300 px-2 py-1" />
              </label>
              <label className="text-sm sm:col-span-2">
                <span className="text-xs text-zinc-500">Notes (optional)</span>
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                  className="mt-0.5 w-full rounded-md border border-zinc-300 px-2 py-1" />
              </label>
            </div>
            {editCount > 0 && <p className="mt-2 text-xs text-amber-700">{editCount} field edit{editCount === 1 ? "" : "s"} will be saved and recorded in the audit trail.</p>}
            {submitError && <div className="mt-3"><ErrorBox message={submitError} /></div>}
            <div className="mt-4 flex gap-2">
              <button onClick={() => submit("approve")} disabled={!!submitting}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
                {submitting === "approve" && <Spinner />} Approve
              </button>
              <button onClick={() => submit("reject")} disabled={!!submitting}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50">
                {submitting === "reject" && <Spinner />} Reject
              </button>
            </div>
          </Card>
        )}

        <AuditTrail events={audit} />
      </div>
    </div>
  );
}
