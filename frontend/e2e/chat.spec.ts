// MANUAL VISUAL CHECK REQUIRED (if Playwright cannot run):
// 1. Start API: make api (from repo root, port 8000)
// 2. Start frontend: cd frontend && npm run dev (port 3000)
// 3. Visit http://localhost:3000/chat
// 4. Verify: meeting dropdown appears (populated from GET /meetings)
// 5. Select a meeting or leave as "All meetings"
// 6. Type "What were the decisions?" and click Ask
// 7. Verify: answer text appears below the form
// 8. Verify: source cards appear with speaker badge, similarity %, content text

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";

test("chat page renders form elements", async ({ page }) => {
  await page.goto(`${BASE_URL}/chat`);
  await expect(page.getByLabel("Meeting")).toBeVisible();
  await expect(page.getByLabel("Question")).toBeVisible();
  await expect(page.getByRole("button", { name: /ask/i })).toBeDisabled();
  await expect(page.getByText("Chunking Strategy")).toBeVisible();
  await expect(page.getByText("Retrieval Strategy")).toBeVisible();
});

test("can type a question and submit (API must be running)", async ({
  page,
}) => {
  await page.goto(`${BASE_URL}/chat`);

  await page.getByLabel("Question").fill("What were the key decisions?");
  await expect(page.getByRole("button", { name: /ask/i })).toBeEnabled();

  await page.getByRole("button", { name: /ask/i }).click();

  // Loading state
  await expect(page.getByRole("button", { name: /searching/i })).toBeVisible();

  // Wait for result
  await expect(page.getByTestId("query-result")).toBeVisible({
    timeout: 30_000,
  });

  // Answer card
  await expect(page.getByText("Answer")).toBeVisible();
});
