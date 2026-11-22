// Dependency-free stand-in for the FastAPI backend, for CSS/UI work only. `npm run dev:mock`
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const fx = path.join(here, "fixtures");
const db = JSON.parse(fs.readFileSync(path.join(fx, "db.json"), "utf8"));
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
