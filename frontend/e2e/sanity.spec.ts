/**
 * DevBuddy E2E Comprehensive Test Suite
 *
 * Frontend (landing, auth): https://devbuddy.org (GitHub Pages)
 * Backend API: https://sivasbrmni-devbuddy.hf.space (HuggingFace Space)
 *
 * Run: npx playwright test e2e/sanity.spec.ts
 */
import { test, expect } from "@playwright/test";

const FRONTEND_URL = "https://devbuddy.org";
const API_URL = process.env.DEVBUDDY_URL || "https://sivasbrmni-devbuddy.hf.space";

// ────────────────────────────────────────────────
// 1. Landing Page Tests
// ────────────────────────────────────────────────
test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
  });

  test("page title is correct", async ({ page }) => {
    await expect(page).toHaveTitle(/DevBuddy/);
  });

  test("hero text is visible", async ({ page }) => {
    await expect(page.getByText("Your AI-powered engineering co-pilot")).toBeVisible();
  });

  test("feature pills are visible", async ({ page }) => {
    await expect(page.getByText("AI Code Review")).toBeVisible();
    await expect(page.getByText("Smart Debugging")).toBeVisible();
    await expect(page.getByText("Dev Metrics")).toBeVisible();
    await expect(page.getByText("Knowledge Base")).toBeVisible();
    await expect(page.getByText("Project Insights")).toBeVisible();
  });

  test("request invite button is present", async ({ page }) => {
    const btn = page.getByRole("button", { name: /Request Invite/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test("trust signals in footer are visible", async ({ page }) => {
    await expect(page.getByText("Open Source")).toBeVisible();
    await expect(page.getByText("Documentation")).toBeVisible();
    await expect(page.getByText("Invite-only private beta")).toBeVisible();
  });

  test("Sign In link navigates to /app", async ({ page }) => {
    const signIn = page.getByRole("link", { name: "Sign In" }).first();
    await expect(signIn).toBeVisible();
    await signIn.click();
    await expect(page).toHaveURL(`${FRONTEND_URL}/app`);
  });

  test("no critical console errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto(`${FRONTEND_URL}/`);
    await page.waitForLoadState("networkidle");
    // CSP may block some external resources; filter known benign errors
    const criticalErrors = errors.filter(e =>
      !e.includes("analytics") &&
      !e.includes("tracking") &&
      !e.includes("Content Security Policy") &&
      !e.includes("Refused to load")
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test("meta description is present", async ({ page }) => {
    const meta = page.locator('meta[name="description"]');
    await expect(meta).toHaveAttribute("content", /engineering/i);
  });
});

// ────────────────────────────────────────────────
// 2. Responsive Layout Tests
// ────────────────────────────────────────────────
test.describe("Responsive Layout", () => {
  test("mobile 320px renders without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto(`${FRONTEND_URL}/`);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });

  test("mobile 390px renders without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${FRONTEND_URL}/`);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });

  test("tablet 768px renders without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(`${FRONTEND_URL}/`);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });

  test("desktop viewport renders full layout", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${FRONTEND_URL}/`);
    await expect(page.getByText("Your AI-powered engineering co-pilot")).toBeVisible();
  });
});

// ────────────────────────────────────────────────
// 3. Auth Flow Tests
// ────────────────────────────────────────────────
test.describe("Auth Flow", () => {
  test("Google OAuth redirect URL is correct", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/app`);

    // The Google sign-in button may navigate same-page or open popup
    await page.getByText(/Continue with Google/i).click();

    // Wait for navigation to Google (same page or popup)
    await page.waitForURL(/accounts\.google\.com/, { timeout: 10000 });
    const url = page.url();

    expect(url).toContain("accounts.google.com");
    expect(url).toContain("oauth");
    expect(url).toContain(encodeURIComponent(`${API_URL}/api/v1/auth/google/callback`));
  });

  test("unauthenticated user sees login gate at /app", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/app`);
    await expect(page.getByText("Sign in to DevBuddy")).toBeVisible();
    await expect(page.getByText(/Continue with Google/i)).toBeVisible();
  });

  test("login gate shows branded heading", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/app`);
    await expect(page.getByText("Your autonomous engineering workspace")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Sign in to DevBuddy/ })).toBeVisible();
  });
});

// ────────────────────────────────────────────────
// 4. API Health Tests
// ────────────────────────────────────────────────
test.describe("API Health", () => {
  test("GET /health returns healthy", async ({ request }) => {
    const resp = await request.get(`${API_URL}/health`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toMatchObject({ status: "healthy", service: "devbuddy-lite" });
  });

  test("GET /health/db returns connected", async ({ request }) => {
    const resp = await request.get(`${API_URL}/health/db`);
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
    const resp = await request.get(`${API_URL}/api/v1/models`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);

    const ollamaModels = body.filter((m: any) => m.provider === "ollama");
    expect(ollamaModels.length).toBeGreaterThan(0);
  });

  test("models have required fields", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/models`);
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
    const resp = await request.get(`${API_URL}/api/v1/nonexistent`);
    expect(resp.status()).toBe(404);
    const body = await resp.json();
    expect(body.detail).toBe("Not found");
  });

  test("settings without token returns 422 validation error", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/settings`);
    expect(resp.status()).toBe(422);
    const body = await resp.json();
    expect(body.detail).toBeDefined();
  });

  test("unknown frontend route falls back to landing page", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/app/nonexistent`);
    await expect(page).toHaveURL(`${FRONTEND_URL}/`);
  });
});

// ────────────────────────────────────────────────
// 7. Performance / Smoke Tests
// ────────────────────────────────────────────────
test.describe("Performance Smoke", () => {
  test("landing page loads within 5 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto(`${FRONTEND_URL}/`);
    await page.waitForLoadState("networkidle");
    const duration = Date.now() - start;
    expect(duration).toBeLessThan(5000);
  });

  test("all static assets return 200", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
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

  test("LCP metric is reasonable", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    await page.waitForLoadState("networkidle");

    const lcp = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const last = entries[entries.length - 1];
          resolve(last?.startTime || 0);
        });
        observer.observe({ entryTypes: ["largest-contentful-paint"] });
        setTimeout(() => resolve(0), 5000);
      });
    });

    if (lcp > 0) {
      expect(lcp).toBeLessThan(3000);
    }
  });
});

// ────────────────────────────────────────────────
// 8. Security Tests
// ────────────────────────────────────────────────
test.describe("Security", () => {
  test("landing page includes CSP meta tag", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    const csp = page.locator('meta[http-equiv="Content-Security-Policy"]');
    await expect(csp).toHaveCount(1);
    const content = await csp.getAttribute("content");
    expect(content).toContain("default-src 'self'");
    expect(content).toContain("frame-ancestors 'none'");
  });

  test("landing page includes referrer policy", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    const referrer = page.locator('meta[name="referrer"]');
    await expect(referrer).toHaveCount(1);
    await expect(referrer).toHaveAttribute("content", "strict-origin-when-cross-origin");
  });
});

// ────────────────────────────────────────────────
// 9. SEO Tests
// ────────────────────────────────────────────────
test.describe("SEO", () => {
  test("Open Graph tags are present", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    await expect(page.locator('meta[property="og:type"]')).toHaveAttribute("content", "website");
    await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /DevBuddy/);
    await expect(page.locator('meta[property="og:description"]')).toHaveAttribute("content", /engineering/);
  });

  test("Twitter card tags are present", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute("content", "summary_large_image");
    await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute("content", /DevBuddy/);
  });

  test("canonical URL is present", async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/`);
    const canonical = page.locator('link[rel="canonical"]');
    await expect(canonical).toHaveCount(1);
    await expect(canonical).toHaveAttribute("href", "https://devbuddy.org");
  });
});
