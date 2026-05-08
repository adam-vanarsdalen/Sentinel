import { test, expect } from "@playwright/test";

const email = process.env.E2E_SUPERADMIN_EMAIL || "platform-admin@example.com";
const password = process.env.E2E_SUPERADMIN_PASSWORD || "ChangeMe!12345";

test("superadmin: create organization and switch context", async ({ page }) => {
  const organizationName = `Northwind Expansion ${Date.now()}`;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("dashboard")).toBeVisible();

  await page.goto("/organizations");
  await expect(page.getByTestId("organizations")).toBeVisible();

  await page.getByRole("button", { name: "Create organization" }).click();
  const createOrganizationDialog = page.getByRole("dialog");
  await createOrganizationDialog.getByPlaceholder("e.g. Northwind Operations").fill(organizationName);
  await createOrganizationDialog.getByRole("button", { name: "Create" }).click();

  const organizationRowLink = page.getByRole("link", { name: organizationName });
  await expect(organizationRowLink).toBeVisible();
  const organizationHref = await organizationRowLink.getAttribute("href");
  expect(organizationHref).toMatch(/\/organizations\/[^/]+$/);
  const tenantId = organizationHref!.split("/").pop()!;

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
