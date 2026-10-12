import { expect, test, type Page } from '@playwright/test';

/** Adaptive practice: "To fix this" after wrong answers, lesson focus links, and the Practice page. */

const LESSON = 'Idempotency keys and duplicate payment requests';
const exercise = (page: Page, title: string) =>
  page.locator('article.exercise', { has: page.getByRole('heading', { name: title }) });

test('a wrong answer points back to the right sections and a similar exercise', async ({ page }) => {
  await page.goto('./#/lesson/idempotency-keys');
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  const rca = exercise(page, 'Charged twice - where is the defect?');
  await rca.getByLabel(/race condition in the server/i).check();
  await rca.getByRole('button', { name: 'Check answer' }).click();

  const fix = rca.locator('.remediation');
  await expect(fix).toContainText('To fix this');
  await fix.getByRole('button', { name: 'Common mistakes and how to debug them' }).click();
  await expect(page.locator('#section-mistakes')).toBeInViewport();

  await rca.scrollIntoViewIfNeeded();
  await fix.getByRole('button', { name: 'Interview: design and test idempotent refunds' }).click();
  await expect(page.locator('#exercise-interview-refund-idempotency')).toBeInViewport();

  // A correct answer needs no fixing.
  await rca.scrollIntoViewIfNeeded();
  await rca.getByRole('button', { name: 'Try again' }).click();
  await rca.getByLabel(/generated a new key/i).check();
  await rca.getByRole('button', { name: 'Check answer' }).click();
  await expect(rca.getByText('Correct.')).toBeVisible();
  await expect(rca.locator('.remediation')).toHaveCount(0);
});

test('a focus link opens the lesson at a collapsed section', async ({ page }) => {
  await page.goto('./#/lesson/idempotency-keys?focus=section-code');
  const code = page.locator('#section-code');
  await expect(code.locator('details')).toHaveAttribute('open', '');
  await expect(code).toBeInViewport();
});

test('practice builds an adaptive session from what you have studied', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-01T09:00:00.000Z'));
  await page.goto('./#/practice');
  await expect(page.getByText('Practice builds on the lessons you have opened.')).toBeVisible();

  // Open the lesson, then practise it.
  await page.goto('./#/lesson/idempotency-keys');
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  await page.getByRole('link', { name: 'Practice', exact: true }).click();
  await expect(page.getByText('Item 1 of 3')).toBeVisible();
  await expect(page.locator('.practice-reason')).toContainText('Not practised yet');

  // Item 1: which requests need protection (answer wrongly first to see the link-style fix).
  const item = page.locator('.review-item');
  await item.getByLabel(/POST \/v1\/refunds/).check();
  await item.getByRole('button', { name: 'Check answer' }).click();
  await expect(item.locator('.remediation a').first()).toHaveAttribute(
    'href',
    /#\/lesson\/idempotency-keys\?focus=section-/,
  );
  await page.getByRole('button', { name: 'Next item' }).click();

  // Item 2: find the race condition.
  await expect(page.getByText('Item 2 of 3')).toBeVisible();
  await item.getByRole('button', { name: /^Line 2:/ }).click();
  await item.getByRole('button', { name: /^Line 7:/ }).click();
  await item.getByRole('button', { name: 'Check lines' }).click();
  await expect(item.getByText('Correct.')).toBeVisible();
  await page.getByRole('button', { name: 'Next item' }).click();

  // Item 3: diagnose the duplicate charge.
  await item.getByLabel(/generated a new key/i).check();
  await item.getByRole('button', { name: 'Check answer' }).click();
  await expect(item.getByText('Correct.')).toBeVisible();
  await page.getByRole('button', { name: 'Finish' }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Practice complete' })).toBeVisible();
  const summary = page.locator('.practice-summary');
  await expect(summary.getByText('The idempotency key contract')).toBeVisible();
  await expect(summary).toContainText('Not started');

  // A new round skips what was just answered and still has work to offer.
  await page.getByRole('button', { name: 'Practise again' }).click();
  await expect(page.getByText(/Item 1 of \d+/)).toBeVisible();
  await expect(page.locator('.practice-reason')).not.toContainText('Not practised yet');
});

test('practice for one lesson, from the lesson page', async ({ page }) => {
  await page.goto('./#/lesson/payment-lifecycle-overview');
  await page.getByRole('link', { name: 'Practise this lesson' }).click();
  await expect(
    page.getByRole('heading', {
      level: 1,
      name: 'Practice: Payment lifecycle - authorise, capture, settle, refund',
    }),
  ).toBeVisible();
  await expect(page.getByText(/from Payment lifecycle/)).toBeVisible();
});
