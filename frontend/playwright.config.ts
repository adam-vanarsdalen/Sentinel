import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const reportDir = process.env.PLAYWRIGHT_REPORT_DIR || "playwright-report";
const testResultsDir = process.env.PLAYWRIGHT_TEST_RESULTS_DIR || "test-results";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 2 : 0,
  outputDir: testResultsDir,
  reporter: [
    ["list"],
    ["html", { outputFolder: reportDir, open: "never" }],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
