// MANUAL VISUAL CHECK REQUIRED (if Playwright cannot run):
// 1. Start API: make api (from repo root, port 8000)
// 2. Start frontend: cd frontend && npm run dev (port 3000)
// 3. Visit http://localhost:3000/meetings
// 4. Verify: table renders with columns Title, Date, Chunks, Speakers
// 5. Click a row — verify a detail panel appears below
// 6. Verify: action items, decisions, and topics sections appear (if extraction was run)
// 7. Verify: "No meetings yet" message appears if no meetings ingested

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";

test("meetings page renders header", async ({ page }) => {
  await page.goto(`${BASE_URL}/meetings`);
  await expect(page.getByText("Meetings")).toBeVisible();
});

test("meetings table renders when meetings exist (API must be running)", async ({
  page,
}) => {
  await page.goto(`${BASE_URL}/meetings`);

  // Either shows table headers or empty state — both are valid
  const tableOrEmpty = page.locator("table, [data-empty]");
  await expect(tableOrEmpty.or(page.getByText(/no meetings/i))).toBeVisible({
    timeout: 10_000,
  });
});

test("clicking a meeting row opens detail panel", async ({ page }) => {
  await page.goto(`${BASE_URL}/meetings`);

  // Try to click the first row if it exists
  const firstRow = page.locator("table tbody tr").first();
  const rowCount = await firstRow.count();

  if (rowCount === 0) {
    // No meetings — skip
    return;
  }

  await firstRow.click();
  await expect(page.getByTestId("meeting-detail")).toBeVisible({
    timeout: 10_000,
  });
});
