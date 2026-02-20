// MANUAL VISUAL CHECK REQUIRED (if Playwright cannot run):
// 1. Start API: make api (from repo root, port 8000)
// 2. Start frontend: cd frontend && npm run dev (port 3000)
// 3. Visit http://localhost:3000
// 4. Drop a .vtt or .txt file onto the drop zone
// 5. Enter a title and click "Upload & Analyse"
// 6. Verify: progress bar appears during upload/extraction
// 7. Verify: extraction results appear — action items, decisions, topics sections
// 8. Verify: chunk count badge and meeting ID are displayed

import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const FIXTURE = path.join(__dirname, "fixtures", "sample.txt");

test.beforeAll(() => {
  // Create a minimal fixture transcript if it doesn't exist
  const dir = path.join(__dirname, "fixtures");
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(FIXTURE)) {
    fs.writeFileSync(
      FIXTURE,
      "Alice: We decided to ship the feature by Friday.\nBob: I'll handle the tests. Due next week.\n",
    );
  }
});

test("upload page renders drop zone and strategy selectors", async ({
  page,
}) => {
  await page.goto(BASE_URL);
  await expect(page.getByTestId("drop-zone")).toBeVisible();
  await expect(page.getByText("Chunking Strategy")).toBeVisible();
  await expect(page.getByText("Retrieval Strategy")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /upload/i }),
  ).toBeDisabled();
});

test("upload transcript and see extraction results", async ({ page }) => {
  await page.goto(BASE_URL);

  // Set title
  await page.getByLabel("Meeting Title").fill("E2E Test Meeting");

  // Upload file via hidden input
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByTestId("drop-zone").click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(FIXTURE);

  // Button should now be enabled
  await expect(
    page.getByRole("button", { name: /upload/i }),
  ).toBeEnabled();

  // Submit
  await page.getByRole("button", { name: /upload/i }).click();

  // Progress text should appear
  await expect(page.getByText(/processing transcript/i)).toBeVisible();

  // Wait for extraction results (API must be running)
  await expect(page.getByTestId("extraction-results")).toBeVisible({
    timeout: 30_000,
  });

  // Ingest summary visible
  await expect(page.getByText(/ingestion complete/i)).toBeVisible();
});
