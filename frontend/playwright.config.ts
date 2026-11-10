import { defineConfig, devices } from "@playwright/test";

// Backend must be running (default http://localhost:8001 here; override with E2E_BACKEND).
const backend = process.env.E2E_BACKEND ?? "http://localhost:8001";
// Dedicated port + --strictPort: never attach to another app that happens to be on the default 5173.
const port = Number(process.env.E2E_PORT ?? 5183);
const adminPort = Number(process.env.E2E_ADMIN_PORT ?? 5184);

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${port}`,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `npm run dev -- --port ${port} --strictPort`,
      url: `http://localhost:${port}`,
      reuseExistingServer: true,
      env: { VITE_PROXY_TARGET: backend },
      timeout: 60_000,
    },
    {
      // The separate admin console (VITE_APP_MODE=admin).
      command: `npm run dev:admin -- --port ${adminPort}`,
      url: `http://localhost:${adminPort}`,
      reuseExistingServer: true,
      env: { VITE_PROXY_TARGET: backend },
      timeout: 60_000,
    },
  ],
});
