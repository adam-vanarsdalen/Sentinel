import { test, expect } from "@playwright/test";

const email = process.env.E2E_SUPERADMIN_EMAIL || "platform-admin@example.com";
const password = process.env.E2E_SUPERADMIN_PASSWORD || "ChangeMe!12345";

test("superadmin: create organization and switch context", async ({ page }) => {
  const firmName = `Northwind Expansion ${Date.now()}`;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("dashboard")).toBeVisible();

  await page.goto("/firms");
  await expect(page.getByTestId("firms")).toBeVisible();

  await page.getByRole("button", { name: "Create organization" }).click();
  const createFirmDialog = page.getByRole("dialog");
  await createFirmDialog.getByPlaceholder("e.g. Northwind Operations").fill(firmName);
  await createFirmDialog.getByRole("button", { name: "Create" }).click();

  const firmRowLink = page.getByRole("link", { name: firmName });
  await expect(firmRowLink).toBeVisible();
  const firmHref = await firmRowLink.getAttribute("href");
  expect(firmHref).toMatch(/\/firms\/[^/]+$/);
  const tenantId = firmHref!.split("/").pop()!;

  await page.evaluate(({ tenantId }) => {
    window.localStorage.setItem("sentinel_tenant_override_enabled", "1");
    window.localStorage.setItem("sentinel_active_tenant_id", tenantId);
    window.dispatchEvent(new Event("sentinel-tenant-change"));
  }, { tenantId });

  await page.goto("/dashboard");
  await expect(page.getByTestId("dashboard")).toBeVisible();
  await expect(page.getByText("Viewing as:")).toBeVisible();

  await page.getByRole("button", { name: "Return to Platform" }).click();
  await expect(page.getByText("Select organization context to view scoped dashboards")).toBeVisible();
});
