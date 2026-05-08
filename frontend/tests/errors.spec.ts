import { expect, test } from "@playwright/test";

const email = process.env.E2E_EMAIL || "admin@demoorg.com";
const password = process.env.E2E_PASSWORD || "ChangeMe!12345";

test("404 page renders custom not-found state", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("dashboard")).toBeVisible();

  await page.goto("/this-page-does-not-exist");
  await expect(page.getByText("404 Not Found")).toBeVisible();
});

test("forbidden routes redirect to the 403 page", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("dashboard")).toBeVisible();
  await page.goto("/organizations");

  await expect(page).toHaveURL(/\/forbidden$/);
  await expect(page.getByText("403 Forbidden")).toBeVisible();
});
