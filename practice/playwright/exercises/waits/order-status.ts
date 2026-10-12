// Exercise - waiting for the result, not for time.
//
// Lesson: "Playwright locators, auto-waiting and web-first assertions". Tests: tests/order-status.spec.ts
// Run: npx playwright test tests/order-status.spec.ts
//
// Both helpers below sleep for a fixed time. Replace the sleeps with web-first assertions (expect on a
// locator), which retry until the condition holds or the timeout ends - no waitForTimeout.
import type { Page } from '@playwright/test';

/**
 * On the order page: waits until the status ([data-testid=order-status]) is SUCCEEDED or FAILED and
 * returns it. Some payments show PENDING first; the page updates the status by itself. Rejects if no
 * final status appears within `timeout` ms.
 */
export async function finalStatus(page: Page, timeout = 10_000): Promise<string> {
  await page.waitForTimeout(5_000);
  return (await page.getByTestId('order-status').textContent()) ?? '';
}

/**
 * On the checkout page: waits until the processing overlay ([data-testid=processing-overlay]) is
 * hidden. Resolves at once if it isn't shown; rejects if it is still shown after `timeout` ms.
 */
export async function processingFinished(page: Page, timeout = 10_000): Promise<void> {
  await page.waitForTimeout(3_000);
}
