import { test, expect } from "@playwright/test";

test("access requires a valid token", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Dashboard access token").fill("wrong");
  await page.getByRole("button", { name: "Connect workspace" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid dashboard token",
  );
  await expect(page.getByLabel("Dashboard access token")).toBeVisible();
});

test("queued manual review completes and persists in history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Dashboard access token").fill("browser-test-token");
  await page.getByRole("button", { name: "Connect workspace" }).click();
  await page
    .getByRole("button", { name: "New review", exact: true })
    .first()
    .click();
  await page.getByLabel("Review name").fill("Browser demo review");
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByRole("button", { name: "Run review" }).click();
  await expect(
    page.getByRole("heading", { name: "Deletion authorization bypass" }),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByText("Demo rule output · not an AI review"),
  ).toBeVisible();
  await page.getByText("Supporting evidence").click();
  await expect(
    page.getByText("can_delete returns True unconditionally", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "All reviews" }).click();
  await page.getByRole("button", { name: "Refresh", exact: false }).click();
  await page.getByLabel("Search reviews").fill("Browser demo");
  await expect(
    page.getByRole("button", {
      name: "Browser demo review Manual diff review",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Benchmarks" }).click();
  await expect(
    page.getByText("A workflow check, not a general accuracy claim."),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile dashboard stays within viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByLabel("Dashboard access token").fill("browser-test-token");
  await page.getByRole("button", { name: "Connect workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Review overview." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
