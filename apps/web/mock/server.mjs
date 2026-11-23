// Dependency-free stand-in for the FastAPI backend, for CSS/UI work only. `npm run dev:mock`
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const fx = path.join(here, "fixtures");
const db = JSON.parse(fs.readFileSync(path.join(fx, "db.json"), "utf8"));
// UI-only fakes for the model picker and the Model stats tab.
const MODELS = [
  { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite", provider: "gemini", free: true, available: true, default: true },
  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash", provider: "gemini", free: true, available: true, default: false },
  { id: "qwen/qwen3.8-27b", label: "Qwen 3.8 27B (Groq)", provider: "groq", free: true, available: true, default: false },
  { id: "nvidia/nemotron-3.5-super-vl:free", label: "Nemotron 3.5 Super VL (OpenRouter)", provider: "openrouter", free: true, available: false, default: false },
  { id: "claude-haiku-5-5", label: "Claude Haiku 5.5 (paid)", provider: "anthropic", free: false, available: false, default: false },
];
const STATS = [
  { model: "gemini-3.5-flash-lite", runs: 4, avg_latency_s: 6.1, avg_cost_usd: 0.0128, avg_tokens: 9100, p50_latency_s: 5.8, p95_latency_s: 8.4, extraction_success_rate: 1, reviewed: 3, edits_per_review: 0.3, flag_dismissal_rate: 0.25, approval_rate: 0.67 },
  { model: "gemini-3.5-flash", runs: 2, avg_latency_s: 9.4, avg_cost_usd: 0, avg_tokens: 11800, p50_latency_s: 9.4, p95_latency_s: 10.2, extraction_success_rate: 1, reviewed: 1, edits_per_review: 0, flag_dismissal_rate: 0, approval_rate: 1 },
  { model: "qwen/qwen3.8-27b", runs: 1, avg_latency_s: 4.2, avg_cost_usd: 0, avg_tokens: 8300, p50_latency_s: null, p95_latency_s: null, extraction_success_rate: 0.67, reviewed: null, edits_per_review: null, flag_dismissal_rate: null, approval_rate: null },
];
const ids = Object.keys(db.details);
db.list.forEach((a, i) => { a.model = MODELS[i % 3].id; });
ids.forEach((id, i) => { db.details[id].model = MODELS[i % 3].id; });

const audit = (id) => [
  { id: 1, ts: "2026-11-21T09:00:00Z", actor: "system", action: "uploaded", detail: { files: 3 } },
  { id: 2, ts: "2026-11-21T09:01:00Z", actor: "system", action: "extracted", detail: { id } },
];

http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  const send = (code, body, type = "application/json") => {
    res.writeHead(code, { "content-type": type, "access-control-allow-origin": "*", "access-control-allow-headers": "*" });
    res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
  };
  if (req.method === "OPTIONS") return send(204, "");
  if (u.pathname === "/models") return send(200, MODELS);
  if (u.pathname === "/stats") return send(200, { models: STATS });
  const p = u.pathname.split("/").filter(Boolean); // applications / :id / (audit|files|review)
  if (p[0] !== "applications") return send(404, { detail: "not found" });
  if (!p[1]) return req.method === "POST" ? send(200, { id: db.list[0].id, status: "in_review" }) : send(200, u.searchParams.get("status") ? db.list.filter((a) => u.searchParams.get("status").split(",").includes(a.status)) : db.list);
  const d = db.details[p[1]];
  if (!d) return send(404, { detail: "not found" });
  if (!p[2]) return send(200, d);
  if (p[2] === "audit") return send(200, audit(p[1]));
  if (p[2] === "review") return send(200, d); // no persistence: UI-only
  if (p[2] === "files") {
    const f = path.join(fx, p[1], path.basename(p[3] ?? ""));
    return fs.existsSync(f) ? send(200, fs.readFileSync(f), "application/pdf") : send(404, { detail: "no file" });
  }
  send(404, { detail: "not found" });
}).listen(8000, "127.0.0.1", () => console.log("mock API on http://127.0.0.1:8000 (no DB, no LLM)"));
