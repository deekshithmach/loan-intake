import { defineConfig } from "@playwright/test";

// Needs the stack running: `docker compose up -d`, the API on :8000 (live LLM), `npm run dev` on :3000.
export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  use: { baseURL: "http://localhost:3000", viewport: { width: 1440, height: 1000 } },
  reporter: "list",
});
