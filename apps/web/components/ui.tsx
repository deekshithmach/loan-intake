import type { Severity, Status } from "@/lib/api";

const STATUS: Record<Status, [string, string]> = {
  processing: ["Processing", "bg-sky-100 text-sky-800"],
  in_review: ["Needs review", "bg-amber-100 text-amber-800"],
  approved: ["Approved", "bg-emerald-100 text-emerald-800"],
  rejected: ["Rejected", "bg-rose-100 text-rose-800"],
  failed: ["Failed", "bg-zinc-200 text-zinc-700"],
};

export function StatusBadge({ status }: { status: Status }) {
  const [text, cls] = STATUS[status] ?? [status, "bg-zinc-100 text-zinc-700"];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status === "processing" && <Spinner className="h-3 w-3" />}
      {text}
    </span>
  );
}

const SEV: Record<Severity, string> = {
  high: "bg-rose-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-zinc-400 text-white",
};

export function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${SEV[severity]}`}>{severity}</span>;
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity=".25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start justify-between gap-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="shrink-0 font-medium underline underline-offset-2">
          Retry
        </button>
      )}
    </div>
  );
}

export function Card({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-zinc-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-zinc-800">{title}</h2>
        {right}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
