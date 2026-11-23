"use client";
import { Card, ErrorBox, Spinner } from "@/components/ui";
import { api, type ModelStats } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const dash = <span className="text-zinc-400" title="not computed yet">—</span>;
const num = (v: number | null, f: (n: number) => string) => (v === null ? dash : f(v));
const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
const usd = (n: number) => (n === 0 ? "free" : `$${n.toFixed(4)}`);

const COLS: { label: string; hint: string; cell: (s: ModelStats) => React.ReactNode }[] = [
  { label: "Runs", hint: "Applications processed with this model", cell: (s) => s.runs },
  { label: "Avg latency", hint: "LLM time per application (all documents, sequential)", cell: (s) => `${s.avg_latency_s.toFixed(1)}s` },
  {
    label: "p50 / p95",
    hint: "Median and slow-tail latency per application",
    cell: (s) => num(s.p50_latency_s, (p50) => `${p50.toFixed(1)}s / ${(s.p95_latency_s ?? 0).toFixed(1)}s`),
  },
  { label: "Avg cost", hint: "Per application at list price; free-tier models show free", cell: (s) => usd(s.avg_cost_usd) },
  { label: "Avg tokens", hint: "Input + output tokens per application", cell: (s) => s.avg_tokens.toLocaleString() },
  { label: "Docs read OK", hint: "Documents extracted without failure", cell: (s) => num(s.extraction_success_rate, pct) },
  { label: "Reviewed", hint: "Applications an underwriter has decided", cell: (s) => (s.reviewed === null ? dash : s.reviewed) },
  { label: "Edits / review", hint: "Fields the underwriter had to correct: a live error signal", cell: (s) => num(s.edits_per_review, (n) => n.toFixed(1)) },
  { label: "False alarms", hint: "Share of flags the underwriter dismissed", cell: (s) => num(s.flag_dismissal_rate, pct) },
  { label: "Approved", hint: "Share of reviewed applications approved", cell: (s) => num(s.approval_rate, pct) },
];

export default function ModelStatsPage() {
  const { data, error, refresh } = usePolling(api.stats, 10000, () => true);
  const rows = data?.models ?? [];

  return (
    <div className="space-y-4">
      <Card title="Model stats" right={<button onClick={refresh} className="text-xs text-zinc-500 hover:text-zinc-900">Refresh</button>}>
        {error && <ErrorBox message={error} onRetry={refresh} />}
        {!data && !error && (
          <div className="flex items-center gap-2 py-8 text-sm text-zinc-500"><Spinner /> Loading…</div>
        )}
        {data && rows.length === 0 && (
          <p className="py-8 text-center text-sm text-zinc-500">
            No runs yet. Create an application and pick a model; each model gets a row here.
          </p>
        )}
        {rows.length > 0 && (
          <div className="-mx-4 -my-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr className="border-b border-zinc-100">
                  <th className="px-4 py-2 font-medium">Model</th>
                  {COLS.map((c) => (
                    <th key={c.label} className="px-4 py-2 text-right font-medium" title={c.hint}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.model} className="border-b border-zinc-50 hover:bg-zinc-50">
                    <td className="px-4 py-2 font-mono text-xs">{s.model}</td>
                    {COLS.map((c) => (
                      <td key={c.label} className="px-4 py-2 text-right tabular-nums">{c.cell(s)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="text-xs text-zinc-500">
        Live numbers from the applications processed here, refreshed every 10 seconds. Uploads have no answer key, so quality shows up
        through what the underwriter does: fields corrected, flags dismissed as false alarms. Benchmark accuracy on 30 synthetic
        applicants with known answers is in the eval report.
      </p>
    </div>
  );
}
