import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

/** Every lesson file: each must open, render all its diagrams and raise no page errors. */
const lessonsDir = join(import.meta.dirname, '..', '..', 'content', 'lessons');
const lessonIds = readdirSync(lessonsDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .flatMap((dir) => readdirSync(join(lessonsDir, dir.name)).filter((f) => f.endsWith('.yaml')))
  .map((file) => file.replace(/\.yaml$/, ''))
  .sort();

test('the home page starts the core path at its first lesson', async ({ page }) => {
  await page.goto('./#/');
  const start = page.locator('.card', { has: page.getByRole('heading', { name: 'Start here' }) });
  await start.getByRole('link', { name: 'Open the first lesson' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Anatomy of an HTTP request and response' }),
  ).toBeVisible();
});

for (const id of lessonIds) {
  test(`lesson ${id} renders with all diagrams`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    await page.goto(`./#/lesson/${id}`);
    await expect(page.locator('main h1')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Practice', exact: true })).toBeVisible();

    const diagrams = page.locator('.diagram');
    const count = await diagrams.count();
    expect(count, 'lesson has no diagrams').toBeGreaterThan(0);
    await expect(page.locator('.diagram[data-rendered="ok"]')).toHaveCount(count, { timeout: 30_000 });
    await expect(page.locator('.diagram[data-rendered="error"]')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
