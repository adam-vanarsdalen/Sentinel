import { expect, test } from "@playwright/test";

const tenantAdminEmail = process.env.E2E_EMAIL || "admin@demoorg.com";
const tenantAdminPassword = process.env.E2E_PASSWORD || "ChangeMe!12345";
const superAdminEmail = process.env.E2E_SUPERADMIN_EMAIL || "platform-admin@example.com";
const superAdminPassword = process.env.E2E_SUPERADMIN_PASSWORD || "ChangeMe!12345";

test("tenant admin can save provider configs, keep secrets masked, and change the default provider", async ({ page }) => {
  const openAiSecret = `provider-test-secret-openai-${Date.now()}`;
  const anthropicSecret = `provider-test-secret-anthropic-${Date.now()}`;

  await page.goto("/login");
  await page.getByLabel("Email").fill(tenantAdminEmail);
  await page.getByLabel("Password").fill(tenantAdminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("dashboard")).toBeVisible();
  await page.goto("/providers");
  await expect(page.getByTestId("provider-settings")).toBeVisible();
  await expect(page.getByTestId("provider-card-ollama")).toBeVisible();

  const openAiCard = page.getByTestId("provider-card-openai");
  await openAiCard.getByLabel("Enable this provider for organization traffic").check();
  await openAiCard.getByTestId("provider-api-key-openai").fill(openAiSecret);
  await openAiCard.getByTestId("provider-default-model-openai").fill("gpt-4.1");
  await openAiCard.getByTestId("provider-allowlist-openai").fill("gpt-4.1");
  await openAiCard.getByTestId("provider-save-openai").click();

  await expect(page.getByTestId("provider-message-openai")).toContainText("Provider settings saved.");
  await expect(openAiCard).toContainText("Configured");
  await expect(openAiCard).toContainText("Default provider");
  await expect(page.locator("body")).not.toContainText(openAiSecret);

  const anthropicCard = page.getByTestId("provider-card-anthropic");
  await anthropicCard.getByLabel("Enable this provider for organization traffic").check();
  await anthropicCard.getByTestId("provider-api-key-anthropic").fill(anthropicSecret);
  await anthropicCard.getByTestId("provider-default-model-anthropic").fill("claude-sonnet-4-6");
  await anthropicCard.getByTestId("provider-allowlist-anthropic").fill("claude-sonnet-4-6");
  await anthropicCard.getByTestId("provider-save-anthropic").click();

  await expect(page.getByTestId("provider-message-anthropic")).toContainText("Provider settings saved.");
  await expect(anthropicCard).toContainText("Configured");
  await expect(page.locator("body")).not.toContainText(anthropicSecret);

  page.once("dialog", (dialog) => dialog.accept());
  await anthropicCard.getByTestId("provider-default-anthropic").click();

  await expect(page.getByTestId("provider-message-anthropic")).toContainText("Default provider updated.");
  await expect(anthropicCard).toContainText("Default provider");
});

test("non-org-admin users cannot manage provider settings", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(superAdminEmail);
  await page.getByLabel("Password").fill(superAdminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("dashboard")).toBeVisible();

  await page.goto("/providers");
  await expect(page).toHaveURL(/\/forbidden$/);
  await expect(page.getByText("403 Forbidden")).toBeVisible();
});
