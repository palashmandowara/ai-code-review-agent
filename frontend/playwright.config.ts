import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "python ../scripts/e2e_server.py",
    url: "http://127.0.0.1:8765/health",
    timeout: 60000,
    reuseExistingServer: false,
  },
});
