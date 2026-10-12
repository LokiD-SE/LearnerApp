// Reference solution - web-first assertions. expect(locator).toHaveText / toBeHidden re-check the page
// until the condition holds (resolving at once if it already does) and fail when the timeout ends.
import { expect, type Page } from '@playwright/test';

export async function finalStatus(page: Page, timeout = 10_000): Promise<string> {
  const status = page.getByTestId('order-status');
  await expect(status).toHaveText(/^(SUCCEEDED|FAILED)$/, { timeout });
  return ((await status.textContent()) ?? '').trim();
}

export async function processingFinished(page: Page, timeout = 10_000): Promise<void> {
  await expect(page.getByTestId('processing-overlay')).toBeHidden({ timeout });
}
