import { expect, test, type Page } from '@playwright/test';

/**
 * Profiles on a shared device: the five default profiles on a fresh browser, adding one with the
 * name rules, switching, each profile's own progress and "Resume study".
 */

// A fresh browser: nobody signed in, no profiles saved yet.
test.use({ storageState: { cookies: [], origins: [] } });

const LESSON = 'Idempotency keys and duplicate payment requests';
const profileList = (page: Page) => page.getByRole('list', { name: 'Profiles' });
const pick = async (page: Page, name: string, pin: string) => {
  await profileList(page)
    .getByRole('button', { name: new RegExp(name) })
    .click();
  await page.getByLabel('PIN', { exact: true }).fill(pin);
  await page.getByRole('button', { name: 'Unlock' }).click();
};
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
  await pick(page, 'Gayu', '4568');
  await expect(page.getByRole('heading', { name: 'Welcome, Gayu' })).toBeVisible();
  await page.goto('./#/lesson/idempotency-keys');
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
  await page.goto('./#/');
  await expect(page.getByRole('link', { name: 'Resume study' })).toBeVisible();

  await switchProfile(page);
  await pick(page, 'Kishore', '2030');
  await expect(page.getByRole('heading', { name: 'Welcome, Kishore' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Resume study' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Start here' })).toBeVisible();

  await switchProfile(page);
  await pick(page, 'Gayu', '4568');
  await page.getByRole('link', { name: 'Resume study' }).click();
  await expect(page.getByRole('heading', { level: 1, name: LESSON })).toBeVisible();
});

test('a profile needs its PIN; a wrong PIN, a PIN change and the forgot-PIN email', async ({ page }) => {
  await page.goto('./#/');
  await profileList(page).getByRole('button', { name: /Raji/ }).click();
  await page.getByLabel('PIN', { exact: true }).fill('4568');
  await page.getByRole('button', { name: 'Unlock' }).click();
  await expect(page.getByRole('alert')).toHaveText('Wrong PIN');

  await page.getByRole('button', { name: 'Change PIN' }).click();
  await page.getByLabel('Current PIN').fill('2030');
  await page.getByLabel('New PIN', { exact: true }).fill('7777');
  await page.getByLabel('Confirm new PIN').fill('7777');
  await page.getByRole('button', { name: 'Change PIN' }).first().click();
  await expect(page.getByRole('status')).toHaveText('PIN changed. Sign in with the new PIN.');

  await page.getByRole('button', { name: 'Forgot PIN?' }).click();
  await expect(page.getByRole('link', { name: 'Email a reset request' })).toHaveAttribute(
    'href',
    /^mailto:lokeshdevamuthu@gmail\.com/,
  );
  await page.getByRole('button', { name: 'Back to sign in' }).click();
  await page.getByLabel('PIN', { exact: true }).fill('7777');
  await page.getByRole('button', { name: 'Unlock' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome, Raji' })).toBeVisible();
});
