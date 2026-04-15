import { test, expect } from "@playwright/test";

test("invalid session token redirects to login", async ({ page, baseURL }) => {
  // Middleware only checks cookie presence, so the app must handle invalid JWTs client-side.
  await page.context().addCookies([
    {
      name: "sentinel_access_token",
      value: "invalid",
      url: baseURL ?? "http://localhost:3000",
    },
  ]);

  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
