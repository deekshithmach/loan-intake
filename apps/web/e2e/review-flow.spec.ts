import { expect, test } from "@playwright/test";
import path from "node:path";

const SAMPLE = path.resolve(__dirname, "../../../data/sample/A0000"); // fake_employer + overdrafts
const SHOTS = path.resolve(__dirname, "screenshots");

test("upload → flags with evidence → edit → decide → audited", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(
    ["paystub.pdf", "w2.pdf", "statement.pdf"].map((f) => path.join(SAMPLE, f)),
  );
  await page.getByRole("button", { name: /Submit 3 documents/ }).click();

  await expect(page).toHaveURL(/\/applications\/APP-/, { timeout: 15_000 });
  await expect(page.getByText("Reading documents…")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/1-processing.png` });

  // live extraction: wait for the review workspace
  await expect(page.getByRole("heading", { name: /Risk flags/ })).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText("Fake employer", { exact: true })).toBeVisible();
  await expect(page.getByText("Overdrafts", { exact: true })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/2-review.png` });

  // evidence chip jumps to the statement and highlights the row
  await page.getByRole("button", { name: /Bank statement · Row \d+/ }).first().click();
  await expect(page.getByRole("tab", { name: "Bank statement", selected: true })).toBeVisible();
  await expect(page.locator("tr.bg-amber-100")).toHaveCount(1);
  await page.screenshot({ path: `${SHOTS}/3-evidence.png` });

  // edit a field on the pay stub and dismiss one flag
  await page.getByRole("tab", { name: "Pay stub" }).click();
  await page.getByLabel("Employee", { exact: true }).fill("SANDRA M. DAVIS");
  await expect(page.getByText("1 field edit will be saved")).toBeVisible();
  const overdraft = page.locator("li", { hasText: "Overdrafts" }).first();
  await overdraft.getByRole("button", { name: "Dismiss" }).click();

  // validation error state: no reviewer name
  await page.getByPlaceholder("Your name").fill("");
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByText("Enter your name before submitting.")).toBeVisible();

  await page.getByPlaceholder("Your name").fill("Priya");
  await page.getByLabel("Notes (optional)").fill("W-2 employer does not match pay stub");
  await page.getByRole("button", { name: "Reject" }).click();

  await expect(page.getByText("Rejected by Priya")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Edited Pay stub › Employee: .* → SANDRA M. DAVIS/)).toBeVisible();
  await expect(page.getByText("Dismissed")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/4-decided.png`, fullPage: true });

  // persisted: reload shows the same final state
  await page.reload();
  await expect(page.getByText("Rejected by Priya")).toBeVisible();
  await expect(page.getByLabel("Employee", { exact: true })).toHaveValue("SANDRA M. DAVIS");

  // the list shows it
  await page.goto("/");
  await expect(page.getByRole("row", { name: /SANDRA M\. DAVIS|SANDRA DAVIS/ }).first()).toContainText("Rejected");
});

test("error state for unknown application", async ({ page }) => {
  await page.goto("/applications/APP-NOPE");
  await expect(page.getByText("application not found")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
