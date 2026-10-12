import { expect, test, type Page } from '@playwright/test';

/**
 * Diagnostic placement: take the core path's placement test, test out of one lesson, see the
 * path skip it, undo it, and test out of another lesson from its own page.
 */

const saveAndContinue = (page: Page) => page.getByRole('button', { name: 'Save and continue' }).click();

test('placement test for the core path, then test out of a single lesson', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-01T09:00:00.000Z'));
  await page.goto('./#/');

  // Offered on the home page until a placement test has been taken.
  const offer = page.locator('.card', {
    has: page.getByRole('heading', { name: 'Already know some of this?' }),
  });
  await offer.getByRole('link', { name: 'Take the placement test' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Placement test: Payments QA - core path' }),
  ).toBeVisible();
  await expect(page.getByText(/questions from 8 lessons/)).toBeVisible();
  await page.getByRole('button', { name: 'Start the test' }).click();

  // Lesson 1's two questions, answered correctly (no feedback is shown during the test).
  await expect(page.getByText(/Question 1 of \d+ · Anatomy of an HTTP request and response/)).toBeVisible();
  await page.getByLabel("The path exists, but it doesn't accept the PUT method.").check();
  await saveAndContinue(page);
  await page.getByRole('button', { name: /^Line 4:/ }).click();
  await saveAndContinue(page);
  await expect(page.locator('.feedback')).toHaveCount(0);

  // Everything else: honest "I don't know".
  const dontKnow = page.getByRole('button', { name: "I don't know this yet" });
  const results = page.getByRole('heading', { level: 1, name: /results$/ });
  for (let i = 0; i < 40 && !(await results.isVisible()); i += 1) await dontKnow.click();

  await expect(results).toBeVisible();
  await expect(page.getByText('You tested out of 1 of 8 lessons.')).toBeVisible();
  const anatomyCard = page.locator('.placement-results li', {
    hasText: 'Anatomy of an HTTP request and response',
  });
  await expect(anatomyCard.locator('.badge-status')).toHaveText('Tested out');
  await anatomyCard.getByText('Review the questions').click();
  await expect(anatomyCard.getByText('Correct', { exact: true }).first()).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Start with: HTTP methods - safety and idempotency' }),
  ).toBeVisible();

  // Home: the offer is gone, the path skips the tested-out lesson, and progress says so.
  await page.getByRole('link', { name: 'Home' }).click();
  await expect(page.getByRole('heading', { name: 'Already know some of this?' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Next on your path' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open the next lesson' })).toBeVisible();
  await expect(page.locator('.path-list li').first()).toContainText(
    '0 completed, 1 tested out of 8 ready lessons',
  );
  await expect(page.locator('.path-list li').first()).toContainText(
    'Next: HTTP methods - safety and idempotency',
  );

  // The recall cards of the tested-out lesson come back for review the next day.
  await page.clock.setFixedTime(new Date('2026-10-02T10:00:00.000Z'));
  await page.reload();
  await expect(page.locator('.nav-link .count')).toHaveText('5');

  // The lesson knows it was tested out; "Study it anyway" undoes that.
  await page.goto('./#/lesson/http-request-response-anatomy');
  await expect(page.locator('.lesson-meta .badge-status')).toHaveText('Tested out');
  await page.getByRole('button', { name: 'Study it anyway' }).click();
  await expect(page.getByRole('link', { name: 'Test out (2 questions)' })).toBeVisible();

  // Test out of another lesson from its own page.
  await page.goto('./#/lesson/http-methods-safety-idempotency');
  await page.getByRole('link', { name: 'Test out (2 questions)' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Test out: HTTP methods - safety and idempotency' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Start the test' }).click();
  await page.getByLabel('GET /v1/orders/123/cancel - cancel the order').check();
  await saveAndContinue(page);
  await page.getByLabel('Yes - the final state is the same; only the response differs.').check();
  await saveAndContinue(page);
  await expect(page.getByText('You tested out of this lesson.', { exact: false })).toBeVisible();

  await page.goto('./#/progress');
  const placementSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Placement results' }),
  });
  await expect(
    placementSection.getByRole('listitem').filter({ hasText: 'HTTP methods - safety and idempotency' }),
  ).toContainText('Tested out');
});

test('a failed lesson test-out recommends studying the lesson', async ({ page }) => {
  await page.goto('./#/placement/lesson/payment-lifecycle-overview');
  await page.getByRole('button', { name: 'Start the test' }).click();
  for (let i = 0; i < 3; i += 1) await page.getByRole('button', { name: "I don't know this yet" }).click();
  await expect(page.getByText('Not yet - study this lesson.', { exact: false })).toBeVisible();
  await page.getByRole('link', { name: 'Study this lesson' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Payment lifecycle - authorise, capture, settle, refund' }),
  ).toBeVisible();
  await expect(page.getByText(/Test out \(3 questions\) - last result 0 of 3/)).toBeVisible();
});

// The "no placement questions yet" state is a component test: every real path now has questions.
test('unknown placement targets', async ({ page }) => {
  await page.goto('./#/placement/path/no-such-path');
  await expect(page.getByRole('heading', { level: 1, name: 'Placement test not found' })).toBeVisible();
  await page.goto('./#/placement/lesson/no-such-lesson');
  await expect(page.getByRole('heading', { level: 1, name: 'Placement test not found' })).toBeVisible();
});
