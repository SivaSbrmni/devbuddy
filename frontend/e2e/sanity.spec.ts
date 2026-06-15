/**
 * DevBuddy E2E Sanity Test Suite
 * Tests the deployed application at the configured BASE_URL.
 *
 * Run: npx playwright test e2e/sanity.spec.ts
 */
import { test, expect } from "@playwright/test";

const BASE_URL = process.env.DEVBUDDY_URL || "https://sivasbrmni-devbuddy.hf.space";

// ────────────────────────────────────────────────
// 1. Landing Page Tests
// ────────────────────────────────────────────────
test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
  });

  test("page title is correct", async ({ page }) => {
    await expect(page).toHaveTitle("DevBuddy Lite");
  });

  test("hero text is visible", async ({ page }) => {
    await expect(page.getByText("Your autonomous engineering partner")).toBeVisible();
  });

  test("feature cards are visible", async ({ page }) => {
    await expect(page.getByText("Autonomous Agents")).toBeVisible();
    await expect(page.getByText("Multi-LLM Routing")).toBeVisible();
    await expect(page.getByText("MCP Tools")).toBeVisible();
    await expect(page.getByText("One-Click Deploy")).toBeVisible();
  });

  test("Google sign-in button is present", async ({ page }) => {
    const btn = page.getByRole("button", { name: /Continue with Google/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test("footer is visible", async ({ page }) => {
    await expect(page.getByText("© 2026 DevBuddy · Autonomous Engineering Platform")).toBeVisible();
  });

  test("no console errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });
});

// ────────────────────────────────────────────────
// 2. Responsive Layout Tests
// ────────────────────────────────────────────────
test.describe("Responsive Layout", () => {
  test("mobile viewport renders without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE_URL}/`);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1); // allow 1px rounding
  });

  test("desktop viewport renders full layout", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/`);
    await expect(page.getByText("Welcome back")).toBeVisible();
  });
});

// ────────────────────────────────────────────────
// 3. Auth Flow Tests
// ────────────────────────────────────────────────
test.describe("Auth Flow", () => {
  test("Google OAuth redirect URL is correct", async ({ page }) => {
    await page.goto(`${BASE_URL}/`);

    // In headless mode Google may navigate same-page; intercept the navigation
    await page.getByRole("button", { name: /Continue with Google/i }).click();

    // Wait for navigation to Google (same page or popup)
    await page.waitForURL(/accounts\.google\.com/, { timeout: 10000 });
    const url = page.url();

    expect(url).toContain("accounts.google.com");
    expect(url).toContain("oauth");
    expect(url).toContain(encodeURIComponent(`${BASE_URL}/api/v1/auth/google/callback`));
  });
});

// ────────────────────────────────────────────────
// 4. API Health Tests
// ────────────────────────────────────────────────
test.describe("API Health", () => {
  test("GET /health returns healthy", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/health`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toMatchObject({ status: "healthy", service: "devbuddy-lite" });
  });

  test("GET /health/db returns connected", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/health/db`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toMatchObject({ status: "healthy", database: "connected" });
  });
});

// ────────────────────────────────────────────────
// 5. Models API Tests
// ────────────────────────────────────────────────
test.describe("Models API", () => {
  test("GET /api/v1/models returns model list", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/api/v1/models`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);

    // Verify Ollama models are present
    const ollamaModels = body.filter((m: any) => m.provider === "ollama");
    expect(ollamaModels.length).toBeGreaterThan(0);
  });

  test("models have required fields", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/api/v1/models`);
    const body = await resp.json();
    for (const model of body) {
      expect(model).toHaveProperty("id");
      expect(model).toHaveProperty("label");
      expect(model).toHaveProperty("provider");
      expect(model).toHaveProperty("family");
      expect(typeof model.id).toBe("string");
      expect(typeof model.label).toBe("string");
    }
  });
});

// ────────────────────────────────────────────────
// 6. Error Handling Tests
// ────────────────────────────────────────────────
test.describe("Error Handling", () => {
  test("404 on unknown API route returns JSON detail", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/api/v1/nonexistent`);
    expect(resp.status()).toBe(404);
    const body = await resp.json();
    expect(body.detail).toBe("Not found");
  });

  test("settings without token returns 422 validation error", async ({ request }) => {
    const resp = await request.get(`${BASE_URL}/api/v1/settings`);
    expect(resp.status()).toBe(422);
    const body = await resp.json();
    expect(body.detail).toBeDefined();
  });

  test("unknown frontend route falls back to landing page", async ({ page }) => {
    await page.goto(`${BASE_URL}/app/nonexistent`);
    await expect(page).toHaveURL(`${BASE_URL}/`);
  });
});

// ────────────────────────────────────────────────
// 7. Performance / Smoke Tests
// ────────────────────────────────────────────────
test.describe("Performance Smoke", () => {
  test("landing page loads within 5 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState("networkidle");
    const duration = Date.now() - start;
    expect(duration).toBeLessThan(5000);
  });

  test("all static assets return 200", async ({ page, request }) => {
    await page.goto(`${BASE_URL}/`);
    const failedAssets: string[] = [];

    page.on("response", async (resp) => {
      if (resp.request().resourceType() === "stylesheet" ||
          resp.request().resourceType() === "script" ||
          resp.request().resourceType() === "image") {
        if (resp.status() >= 400) {
          failedAssets.push(resp.url());
        }
      }
    });

    await page.waitForLoadState("networkidle");
    expect(failedAssets).toHaveLength(0);
  });
});
