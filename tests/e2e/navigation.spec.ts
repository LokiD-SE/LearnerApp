import { expect, test, type Page } from '@playwright/test';

/**
 * Getting around: a way back to the home page from every page, and the course outline beside
 * a course and a lesson - every course with its chapters, lessons and sections, each with its
 * study time.
 */

const HOME = 'Learn it, practise it, prove it.';
const LESSON = 'Idempotency keys and duplicate payment requests';

const outline = (page: Page) => page.getByRole('navigation', { name: 'Courses' });

/** Beside the page on desktop; a collapsed panel on a phone that has to be opened first. */
async function openOutline(page: Page) {
  const panel = outline(page);
  const toggle = panel.locator('summary').first();
  if (test.info().project.name === 'mobile') {
    await expect(panel.getByRole('link', { name: 'Course overview' }).first()).toBeHidden();
    await toggle.click();
  }
  return panel;
}

const pages = [
  './#/learn',
  './#/learn?subject=java',
  './#/learn?stage=stage-2',
  './#/lesson/idempotency-keys',
  './#/lesson/test-design-techniques',
  './#/lesson/no-such-lesson',
  './#/review',
  './#/practice',
  './#/interview',
  './#/progress',
  './#/search?q=idempotency',
  './#/placement/path/payments-qa-core',
  './#/no-such-page',
];

for (const path of pages) {
  test(`back to home from ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('main h1')).toBeVisible();
    await page.getByRole('link', { name: 'Back to home' }).click();
    await expect(page.getByRole('heading', { level: 1, name: HOME })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to home' })).toHaveCount(0);
  });
}

test('a lesson shows its course outline, its sections and their times', async ({ page }) => {
  await page.goto('./#/lesson/idempotency-keys');
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  const panel = await openOutline(page);

  // The current course is open with its chapters; the current lesson is marked.
  const current = panel.locator('.course-list > li.is-current');
  await expect(current).toHaveCount(1);
  await expect(current.locator('summary').first()).toContainText('API testing and payment API testing');
  await expect(current.locator('summary').first().locator('time')).toHaveText(/\d+ (h|min)/);
  await expect(
    current.locator('.chapter-name', { hasText: 'Payment API testing' }).locator('time'),
  ).toBeVisible();
  const here = panel.getByRole('link', { name: LESSON });
  await expect(here).toHaveAttribute('aria-current', 'page');
  await expect(panel.locator('.is-here .outline-row time')).toHaveText('50 min');

  // The lesson's sections sit under it with their times, and jump to the section.
  const sections = panel.getByRole('list', { name: 'Sections of this lesson' });
  await expect(sections.getByRole('button', { name: 'Objectives' })).toBeVisible();
  const times = await sections.locator('time').allTextContents();
  const minutes = times.map((text) => Number(/^(\d+) min$/.exec(text)?.[1]));
  expect(minutes.every((m) => m >= 1)).toBe(true);
  expect(minutes.reduce((a, b) => a + b, 0)).toBe(50);
  await sections.getByRole('button', { name: 'Why it exists - the ambiguous timeout' }).click();
  await expect(page.locator('#section-why')).toBeInViewport();
  await expect(page.locator('#section-why .section-kind time')).toHaveText(/^\d+ min$/);

  // Other courses are listed, closed, and lead to their course page.
  const java = panel.locator('.course-list > li', { hasText: 'Java for interviews and automation' });
  await java.locator('summary').first().click();
  await java.getByRole('link', { name: 'Course overview' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Java for interviews and automation' }),
  ).toBeVisible();
});

test('a course page totals its time and lists its chapters beside it', async ({ page }) => {
  await page.goto('./#/learn?subject=java');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Java for interviews and automation' }),
  ).toBeVisible();
  await expect(page.locator('.time-summary').first()).toHaveText(/^\d+ h( \d+ min)? for 8 lessons$/);
  await expect(page.locator('.module h3').first().locator('time')).toHaveText(/\d+ (h|min)/);
  await expect(page.locator('.lesson-list li').first().locator('time')).toHaveText(/^\d+ min$/);

  const panel = await openOutline(page);
  await expect(panel.getByRole('link', { name: 'Course overview' }).first()).toBeVisible();
  await expect(panel.locator('.course-list > li.is-current')).toContainText('Java basics');

  // A course with planned lessons says so, with a rough figure for them.
  await page.goto('./#/learn?subject=api-testing');
  await expect(page.locator('.time-summary').first()).toContainText(/planned lessons?, about \d+/);
});
