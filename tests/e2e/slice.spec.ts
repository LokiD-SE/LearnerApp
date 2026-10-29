import { expect, test, type Page } from '@playwright/test';

/**
 * The first vertical slice, end to end against the production build:
 * curriculum -> lesson -> exercise -> feedback -> saved -> reload -> restored,
 * then the spaced review two days later, plus empty and error states.
 */

const T0 = new Date('2026-10-01T09:00:00.000Z');
const DAY = 24 * 60 * 60 * 1000;
const LESSON = 'Idempotency keys and duplicate payment requests';

async function openLessonFromCurriculum(page: Page) {
  await page.goto('./#/learn');
  await expect(page.getByRole('heading', { level: 1, name: 'Curriculum' })).toBeVisible();
  await page.locator('.lesson-list').getByRole('link', { name: LESSON }).click();
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
}

const exercise = (page: Page, title: string) =>
  page.locator('article.exercise', { has: page.getByRole('heading', { name: title }) });

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(T0);
});

test('learn, practise, save, reload and resume', async ({ page }) => {
  await page.goto('./');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Learn it, practise it, prove it.' }),
  ).toBeVisible();
  await expect(page.getByText('Nothing due.')).toBeVisible();

  await openLessonFromCurriculum(page);
  await expect(page.getByRole('heading', { name: 'Learning objectives' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Why it exists - the ambiguous timeout' })).toBeVisible();

  // Diagrams render (Mermaid, lazily loaded from the bundle).
  await expect(page.locator('.diagram[data-rendered="ok"] svg').first()).toBeVisible({ timeout: 20_000 });

  // A wrong answer gets misconception feedback, not the solution.
  const rca = exercise(page, 'Charged twice - where is the defect?');
  await rca.getByLabel(/race condition in the server/i).check();
  await rca.getByRole('button', { name: 'Check answer' }).click();
  await expect(rca.getByText('Not yet.')).toBeVisible();
  await expect(rca.getByText(/A race needs two requests with the/)).toBeVisible();
  await expect(rca.getByRole('heading', { name: 'Worked solution' })).toHaveCount(0);

  // Progressive hint, then a correct retry and the worked solution.
  await rca.getByRole('button', { name: 'Show hint 1 of 2' }).click();
  await expect(rca.getByRole('list', { name: 'Hints' })).toContainText('What does the server use to decide');
  await rca.getByRole('button', { name: 'Try again' }).click();
  await rca.getByLabel(/generated a new key/i).check();
  await rca.getByRole('button', { name: 'Check answer' }).click();
  await expect(rca.getByText('Correct.')).toBeVisible();
  await rca.getByRole('button', { name: 'Show worked solution' }).click();
  await expect(rca.getByRole('heading', { name: 'Worked solution' })).toBeVisible();
  await expect(rca.getByRole('heading', { name: 'Try this next' })).toBeVisible();

  // Ordering exercise with the keyboard-accessible move buttons.
  const order = exercise(page, "Order the server's steps");
  await order.getByRole('button', { name: 'Check order' }).click();
  await expect(order.locator('.feedback')).toContainText('steps are in the right position');

  // Bookmark, notes, mark as read.
  await page.getByRole('button', { name: '☆ Bookmark' }).click();
  await page.getByLabel('My notes').fill('Ask the team how long SandPay keeps keys.');
  await page.getByRole('button', { name: 'Mark as read' }).click();
  await expect(page.getByText(/Marked as read on/)).toBeVisible();
  await page.waitForTimeout(600); // notes are saved after a short pause in typing

  // Reload: everything is restored from localStorage.
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  await expect(page.getByText(/Marked as read on/)).toBeVisible();
  await expect(page.getByRole('button', { name: '★ Bookmarked' })).toBeVisible();
  await expect(page.getByLabel('My notes')).toHaveValue('Ask the team how long SandPay keeps keys.');
  await expect(exercise(page, 'Charged twice - where is the defect?').locator('.last-result')).toContainText(
    'Last result 0%',
  );
  await expect(page.locator('.lesson-meta .badge-status')).toHaveText('In progress');

  // Home offers to resume, and progress shows the evidence.
  await page.goto('./#/');
  await expect(page.getByRole('heading', { name: 'Continue' })).toBeVisible();
  await page.getByRole('link', { name: 'Resume study' }).click();
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  await page.goto('./#/progress');
  await expect(page.getByRole('heading', { level: 1, name: 'Progress' })).toBeVisible();
  await expect(page.getByRole('row', { name: /Diagnosing duplicate charges/ })).toContainText('Attempted');
  await expect(page.getByRole('link', { name: LESSON }).first()).toBeVisible();
});

test('items come back for review two days later', async ({ page }) => {
  await openLessonFromCurriculum(page);
  await page.getByRole('button', { name: 'Mark as read' }).click();
  const rca = exercise(page, 'Charged twice - where is the defect?');
  await rca.getByLabel(/generated a new key/i).check();
  await rca.getByRole('button', { name: 'Check answer' }).click();
  await expect(rca.getByText('Correct.')).toBeVisible();

  // Nothing is due straight away.
  await page.goto('./#/review');
  await expect(page.getByText('Nothing is due right now.')).toBeVisible();

  // Two days later the recall cards and the exercise are due, interleaved.
  await page.clock.setFixedTime(new Date(T0.getTime() + 2 * DAY));
  await page.reload();
  await expect(page.locator('.nav-link .count')).toHaveText('7');
  await expect(page.getByText(/Item 1 of 7/)).toBeVisible();

  for (let i = 0; i < 7; i += 1) {
    const item = page.locator('.review-item');
    if (await item.getByRole('button', { name: 'Show answer' }).count()) {
      await item.getByRole('button', { name: 'Show answer' }).click();
      await item.getByRole('button', { name: 'Knew it' }).click();
    } else {
      await item.getByLabel(/generated a new key/i).check();
      await item.getByRole('button', { name: 'Check answer' }).click();
      await expect(item.getByText('Correct.')).toBeVisible();
    }
    await page.getByRole('button', { name: i === 6 ? 'Finish' : 'Next item' }).click();
  }
  await expect(page.getByRole('heading', { level: 1, name: 'Review complete' })).toBeVisible();
  await page.goto('./#/progress');
  // Evidence now: the analysis exercise (lesson + review) and two recall cards, all right, the
  // second time more than a day later. The interview question is still unanswered, so coverage
  // is 7/10 - below the 75% needed for Proficient: the model calls this Practising, and retained.
  const row = page.getByRole('row', { name: /Diagnosing duplicate charges/ });
  await expect(row).toContainText('Practising');
  await expect(row.locator('td').last()).toHaveText('Yes');
});

test('empty, planned, not-found and corrupt-storage states', async ({ page }) => {
  await page.goto('./#/search?q=zebra%20giraffe');
  await expect(page.getByText(/No lessons mention all of those words/)).toBeVisible();

  await page.goto('./#/search?q=idempotency');
  await expect(page.locator('.search-results').getByRole('link', { name: LESSON })).toBeVisible();

  await page.goto('./#/learn');
  await page.getByLabel('Filter').fill('no such lesson anywhere');
  await expect(page.getByText('No lessons match. Try clearing a filter.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator('.lesson-list').getByRole('link', { name: LESSON })).toBeVisible();

  // Every curriculum lesson is written now, so a former planned lesson opens as a lesson.
  await page.goto('./#/lesson/e2e-payment-capstone');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Capstone - an end-to-end payment journey' }),
  ).toBeVisible();
  await expect(page.getByText(/This lesson is planned but not written yet/)).toHaveCount(0);

  await page.goto('./#/lesson/does-not-exist');
  await expect(page.getByRole('heading', { level: 1, name: 'Lesson not found' })).toBeVisible();

  await page.goto('./#/nowhere');
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible();

  await page.evaluate(() => localStorage.setItem('learnerapp.profile.loki.progress.v1', '{broken'));
  await page.goto('./#/');
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Saved progress could not be loaded');
  await page.getByRole('button', { name: 'Dismiss' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('zoomable and no horizontal page scroll', async ({ page }) => {
  await openLessonFromCurriculum(page);
  const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
  expect(viewport).not.toMatch(/maximum-scale|user-scalable\s*=\s*no/);
  await expect(page.locator('.diagram[data-rendered="ok"] svg').first()).toBeVisible({ timeout: 20_000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
