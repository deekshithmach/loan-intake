// Display helpers. Money from the API is integer cents.
export const MONEY_FIELDS = new Set([
  "gross", "net", "ytd_gross",
  "wages_box1", "federal_tax_box2", "ss_wages_box3", "ss_tax_box4", "medicare_wages_box5", "medicare_tax_box6",
  "opening_balance", "closing_balance", "amount", "balance",
  "federal_tax", "social_security", "medicare", "state_tax", "health_insurance",
]);
export const INT_FIELDS = new Set(["year"]);
export const DOC_LABELS: Record<string, string> = { paystub: "Pay stub", w2: "W-2", statement: "Bank statement" };
export const DOC_ORDER = ["paystub", "w2", "statement"];

export function usd(cents: unknown): string {
  if (typeof cents !== "number") return String(cents ?? "—");
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

/** Value as shown in an input: money as "4,115.38", everything else as text. */
export function display(field: string, v: unknown): string {
  if (v === null || v === undefined) return "";
  if (MONEY_FIELDS.has(field) && typeof v === "number")
    return (v / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}

export function label(field: string): string {
  const s = field.replace(/_box(\d+)/, " (box $1)").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/\bytd\b/i, "YTD").replace(/\bein\b/i, "EIN").replace(/\bssn\b/i, "SSN");
}

export function when(iso: string): string {
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function humanize(code: string): string {
  return code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}
