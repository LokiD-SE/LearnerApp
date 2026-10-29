import { expect, test, type Page } from '@playwright/test';

/**
 * Profiles on a shared device: the five default profiles on a fresh browser, adding one with the
 * name rules, switching, each profile's own progress and "Resume study".
 */

// A fresh browser: nobody signed in, no profiles saved yet.
test.use({ storageState: { cookies: [], origins: [] } });

const LESSON = 'Idempotency keys and duplicate payment requests';
const profileList = (page: Page) => page.getByRole('list', { name: 'Profiles' });
const switchProfile = (page: Page) => page.getByRole('button', { name: 'Switch profile' }).click();

test('a fresh browser shows the five profiles; a new profile follows the name rules', async ({ page }) => {
  await page.goto('./#/');
  await expect(page.getByRole('heading', { level: 1, name: 'Who is learning?' })).toBeVisible();
  for (const name of ['Loki', 'Gayu', 'Kishore', 'Saurabh', 'Raji']) {
    await expect(profileList(page).getByRole('button', { name: new RegExp(name) })).toBeVisible();
  }

  const input = page.getByLabel('First name');
  await input.fill('Mary Ann');
  await expect(page.getByRole('alert')).toHaveText('Please enter a single-word first name with no spaces');
  await input.fill('R2D2');
  await expect(page.getByRole('alert')).toHaveText('Please enter a single-word first name with no spaces');
  await input.fill('loki');
  await expect(page.getByRole('alert')).toHaveText('There is already a profile called Loki');

  await input.fill('  priya  ');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Add and start' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome, Priya' })).toBeVisible();

  // The session survives a reload, and switching shows the new profile alongside the others.
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Welcome, Priya' })).toBeVisible();
  await switchProfile(page);
  await expect(profileList(page).getByRole('listitem')).toHaveCount(6);
  await expect(profileList(page).getByRole('button', { name: /Priya/ })).toBeVisible();
});

test('each profile keeps its own progress and resumes where it stopped', async ({ page }) => {
  await page.goto('./#/');
  await profileList(page).getByRole('button', { name: /Gayu/ }).click();
  await expect(page.getByRole('heading', { name: 'Welcome, Gayu' })).toBeVisible();
  await page.goto('./#/lesson/idempotency-keys');
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  await page.goto('./#/');
  await expect(page.getByRole('link', { name: 'Resume study' })).toBeVisible();

  await switchProfile(page);
  await profileList(page)
    .getByRole('button', { name: /Kishore/ })
    .click();
  await expect(page.getByRole('heading', { name: 'Welcome, Kishore' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Resume study' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Start here' })).toBeVisible();

  await switchProfile(page);
  await profileList(page).getByRole('button', { name: /Gayu/ }).click();
  await page.getByRole('link', { name: 'Resume study' }).click();
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
});
