"use client";
import { useEffect, useRef } from "react";

import type { AuditEvent, Evidence, Extraction, Flag } from "@/lib/api";
import { DOC_LABELS, MONEY_FIELDS, display, humanize, label, usd, when } from "@/lib/format";

import { Card, ErrorBox, SeverityPill } from "./ui";

export type Edits = Record<string, Record<string, string>>;

const topField = (e: Evidence | null) => e?.field.split(".")[0];
const txnIndex = (e: Evidence | null) => (e?.field.startsWith("transactions.") ? Number(e.field.split(".")[1]) : -1);

function evidenceValue(e: Evidence): string {
  const leaf = e.field.split(".").pop() ?? "";
  if (typeof e.value === "number" && (MONEY_FIELDS.has(leaf) || e.field.startsWith("transactions."))) return usd(e.value);
  return e.value === null || e.value === undefined ? "" : String(e.value);
}

// ---- Flags ---------------------------------------------------------------------------
export function FlagsPanel({ flags, editable, decisions, setDecision, onEvidence }: {
  flags: Flag[];
  editable: boolean;
  decisions: Record<string, "accept" | "dismiss">;
  setDecision: (code: string, d: "accept" | "dismiss") => void;
  onEvidence: (e: Evidence) => void;
}) {
  return (
    <Card title={`Risk flags (${flags.length})`}>
      {flags.length === 0 && <p className="text-sm text-emerald-700">No issues found. All checks passed.</p>}
      <ul className="space-y-3">
        {flags.map((f, i) => {
          const d = f.decision ?? decisions[f.code] ?? "accept";
          return (
            <li key={`${f.code}-${i}`} className={`rounded-lg border p-3 ${d === "dismiss" ? "border-zinc-200 opacity-60" : "border-rose-200 bg-rose-50/40"}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <SeverityPill severity={f.severity} />
                    <span className="text-sm font-semibold">{humanize(f.code)}</span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-700">{f.message}</p>
                </div>
                {editable ? (
                  <div className="flex shrink-0 overflow-hidden rounded-md border border-zinc-300 text-xs">
                    {(["accept", "dismiss"] as const).map((opt) => (
                      <button key={opt} onClick={() => setDecision(f.code, opt)}
                        className={`px-2 py-1 capitalize ${d === opt ? "bg-zinc-900 text-white" : "bg-white hover:bg-zinc-100"}`}>
                        {opt === "accept" ? "Valid" : "Dismiss"}
                      </button>
                    ))}
                  </div>
                ) : (
                  <span className="shrink-0 text-xs text-zinc-500">{d === "dismiss" ? "Dismissed" : "Confirmed"}</span>
                )}
              </div>
              {f.evidence.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {f.evidence.map((e, j) => (
                    <li key={j}>
                      <button onClick={() => onEvidence(e)} title={e.note}
                        className="rounded border border-zinc-300 bg-white px-2 py-0.5 text-left text-xs hover:border-zinc-900">
                        <span className="text-zinc-500">{DOC_LABELS[e.doc] ?? e.doc} · </span>
                        {e.field.startsWith("transactions.")
                          ? `Row ${Number(e.field.split(".")[1]) + 1}${e.field.split(".")[2] ? ` ${e.field.split(".")[2]}` : ""}`
                          : label(e.field)}
                        {evidenceValue(e) && <span className="ml-1 font-mono">{evidenceValue(e)}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

// ---- Extracted fields for one document ---------------------------------------------
export function DocFields({ docKey, ex, editable, edits, setEdit, focus }: {
  docKey: string;
  ex: Extraction | undefined;
  editable: boolean;
  edits: Edits;
  setEdit: (doc: string, field: string, value: string, original: string) => void;
  focus: Evidence | null;
}) {
  const focusRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    focusRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); // braces: effects must not return a value
  }, [focus]);

  if (!ex) return <p className="text-sm text-zinc-500">This document was not provided.</p>;
  const u = ex.usage;
  const meta = (
    <p className="mb-3 text-xs text-zinc-500">
      {ex.scanned ? "Scanned image → vision model" : "Text PDF"} · {ex.attempts} attempt{ex.attempts === 1 ? "" : "s"} ·{" "}
      {(u.input_tokens + u.output_tokens).toLocaleString()} tokens · ${u.cost_usd.toFixed(4)} · {(u.latency_ms / 1000).toFixed(1)}s
    </p>
  );
  if (!ex.ok || !ex.data) return <>{meta}<ErrorBox message={`Extraction failed: ${ex.error ?? "unknown error"}`} /></>;

  const mine = focus?.doc === docKey ? focus : null;
  const scalars = Object.entries(ex.data).filter(([, v]) => v === null || typeof v !== "object");
  const deductions = ex.data.deductions as Record<string, number> | undefined;
  const txns = ex.data.transactions as { date: string; description: string; amount: number; balance: number }[] | undefined;

  return (
    <div>
      {meta}
      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
        {scalars.map(([field, v]) => {
          const original = display(field, v);
          const value = edits[docKey]?.[field] ?? original;
          const changed = value !== original;
          const hot = topField(mine) === field;
          return (
            <div key={field} ref={hot ? (el) => { focusRef.current = el; } : undefined}
              className={`rounded-md ${hot ? "ring-2 ring-amber-400 ring-offset-2" : ""}`}>
              <dt className="text-xs text-zinc-500">{label(field)}{changed && <span className="ml-1 text-amber-700">(edited)</span>}</dt>
              <dd>
                <input value={value} disabled={!editable} aria-label={label(field)}
                  onChange={(e) => setEdit(docKey, field, e.target.value, original)}
                  className={`w-full rounded-md border px-2 py-1 font-mono text-sm disabled:border-transparent disabled:bg-transparent disabled:px-0 ${
                    changed ? "border-amber-400 bg-amber-50" : "border-zinc-300"}`} />
                {changed && <span className="text-[11px] text-zinc-500">was {original}</span>}
              </dd>
            </div>
          );
        })}
      </dl>

      {deductions && (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Deductions (this period)</h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
            {Object.entries(deductions).map(([k, v]) => (
              <div key={k}><dt className="text-xs text-zinc-500">{label(k)}</dt><dd className="font-mono">{usd(v)}</dd></div>
            ))}
          </dl>
        </div>
      )}

      {txns && (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Transactions ({txns.length})</h3>
          <div className="max-h-80 overflow-auto rounded-md border border-zinc-200">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-zinc-50 text-left text-zinc-500">
                <tr><th className="px-2 py-1">#</th><th className="px-2 py-1">Date</th><th className="px-2 py-1">Description</th>
                  <th className="px-2 py-1 text-right">Amount</th><th className="px-2 py-1 text-right">Balance</th></tr>
              </thead>
              <tbody className="font-mono">
                {txns.map((t, i) => {
                  const hot = txnIndex(mine) === i;
                  return (
                    <tr key={i} ref={hot ? (el) => { focusRef.current = el; } : undefined}
                      className={`border-t border-zinc-100 ${hot ? "bg-amber-100" : ""}`}>
                      <td className="px-2 py-0.5 text-zinc-400">{i + 1}</td>
                      <td className="px-2 py-0.5">{t.date}</td>
                      <td className="px-2 py-0.5 font-sans">{t.description}</td>
                      <td className={`px-2 py-0.5 text-right ${t.amount > 0 ? "text-emerald-700" : ""}`}>{usd(t.amount)}</td>
                      <td className={`px-2 py-0.5 text-right ${t.balance < 0 ? "font-semibold text-rose-700" : ""}`}>{usd(t.balance)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Audit trail ----------------------------------------------------------------------
function describe(e: AuditEvent): string {
  const d = e.detail as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  switch (e.action) {
    case "uploaded": return `Uploaded ${(d.files ?? []).join(", ")}`;
    case "extracted": return `Extracted ${Object.keys(d.docs ?? {}).length} documents · ${d.llm_calls} LLM calls · $${Number(d.cost_usd ?? 0).toFixed(4)}`;
    case "flags_raised": return d.codes?.length ? `Raised flags: ${d.codes.map(humanize).join(", ")}` : "All checks passed";
    case "review_submitted": return `Submitted decision: ${d.decision}`;
    case "field_edited": return `Edited ${DOC_LABELS[d.doc] ?? d.doc} › ${label(d.field)}: ${display(d.field, d.old)} → ${display(d.field, d.new)}`;
    case "approved": case "rejected": return `${humanize(e.action)}${d.notes ? ` · “${d.notes}”` : ""}`;
    case "failed": return `Processing failed: ${d.error}`;
    default: return JSON.stringify(d);
  }
}

export function AuditTrail({ events }: { events: AuditEvent[] | null }) {
  return (
    <Card title="Audit trail">
      {!events ? <p className="text-sm text-zinc-500">Loading…</p> : (
        <ol className="relative space-y-3 border-l border-zinc-200 pl-4">
          {events.map((e) => (
            <li key={e.id} className="text-sm">
              <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-zinc-400" />
              <div className="text-xs text-zinc-500">{when(e.ts)} · {e.actor}</div>
              <div>{describe(e)}</div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
