import { expect, test, type Locator } from '@playwright/test';

/**
 * Interview practice: generate an interview for a course, take round 1 with a hint and a skip,
 * read the report, retake the round and see the improvement, then the attempt history.
 * The interview is random by design, so the test relies only on what every startup-style
 * interview has: round 1 is the intro call, whose questions are all written answers.
 */

const ANSWER =
  'In my last project I owned checkout testing; I raised the risk with evidence and we fixed it.';

async function answerInWriting(question: Locator, ticks: 'all' | number) {
  await question.getByRole('textbox').fill(ANSWER);
  await question.getByRole('button', { name: 'Compare with the model answer' }).click();
  const points = question.locator('fieldset.rubric input[type="checkbox"]');
  const count = ticks === 'all' ? await points.count() : ticks;
  for (let i = 0; i < count; i += 1) await points.nth(i).check();
  await question.getByRole('button', { name: 'Save my self-assessment' }).click();
}

test('generate an interview, take a round, read the report, retake it and compare', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-12T09:00:00.000Z'));
  await page.goto('./#/');
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Interview' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Interview practice' })).toBeVisible();

  // The researched company loops, with their sources.
  await page.locator('summary', { hasText: 'Google' }).click();
  await expect(
    page.getByRole('link', { name: /Googleyness and leadership interview questions/ }),
  ).toBeVisible();

  await page.getByLabel('Course').selectOption({ label: 'Payments QA - core path' });
  await page.getByLabel('Company style').selectOption({ label: 'Startups' });
  await page.getByRole('button', { name: 'Generate interview' }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Startups interview' })).toBeVisible();
  await expect(page.getByText('For Payments QA - core path')).toBeVisible();
  await page.getByRole('button', { name: 'Start the interview' }).click();

  await expect(page.getByRole('heading', { level: 1, name: /^Round 1 of \d+: Intro call$/ })).toBeVisible();
  await page.getByRole('button', { name: 'Start round 1' }).click();
  await expect(page.locator('.round-timer')).toBeVisible();

  const questions = page.locator('article.interview-question');
  await expect(questions).toHaveCount(3);

  // Question 1: a hint (costs 15%), then a full answer. Question 2: skipped. Question 3: partly.
  await questions
    .nth(0)
    .getByRole('button', { name: /^Show hint 1 of/ })
    .click();
  await expect(questions.nth(0).getByRole('list', { name: 'Hints' })).toBeVisible();
  await answerInWriting(questions.nth(0), 'all');
  await expect(questions.nth(0).getByText('Score 85%')).toBeVisible();
  await expect(questions.nth(0).getByRole('heading', { name: 'Model answer' })).toBeVisible();

  await questions.nth(1).getByRole('button', { name: 'Skip and show the answer' }).click();
  await expect(questions.nth(1).getByText('Skipped.')).toBeVisible();

  await answerInWriting(questions.nth(2), 1);
  await expect(questions.nth(2).getByText(/^You covered 1 of \d points\.$/)).toBeVisible();

  await page.getByRole('button', { name: 'Finish round and see my report' }).click();
  const report = page.getByRole('region', { name: 'Round report' });
  await expect(report).toBeVisible();
  await expect(report.getByText(/first finished attempt at this round/)).toBeVisible();
  await expect(report.getByRole('heading', { name: 'Areas to improve' })).toBeVisible();
  await expect(report.getByRole('heading', { name: 'What went well' })).toBeVisible();
  await expect(report.getByText(/most likely read as/)).toBeVisible();
  const firstScore = Number(
    (await report.locator('.round-score .stat-value').textContent())!.replace('%', ''),
  );

  // Retake the round: every point covered, no hints.
  await page.getByRole('button', { name: 'Retake this round' }).click();
  await expect(page.locator('.round-timer')).toBeVisible();
  await expect(page.getByText(/attempt 2/)).toBeVisible();
  for (let i = 0; i < 3; i += 1) await answerInWriting(questions.nth(i), 'all');
  await page.getByRole('button', { name: 'Finish round and see my report' }).click();
  await expect(report.locator('.round-score .stat-value')).toHaveText('100%');
  await expect(
    report.getByText(`Up ${100 - firstScore} points on your previous attempt (${firstScore}%).`),
  ).toBeVisible();
  await expect(report.getByRole('list', { name: 'This round in every attempt' }).locator('li')).toHaveCount(
    2,
  );

  // The interview page compares attempts round by round, and survives a reload.
  await page.getByRole('link', { name: 'Back to the interview' }).click();
  await page.reload();
  const history = page.getByRole('table');
  await expect(history.getByRole('columnheader', { name: /Attempt 1/ })).toBeVisible();
  await expect(history.getByRole('columnheader', { name: /Attempt 2/ })).toBeVisible();
  const firstRow = history.getByRole('row', { name: /1\. Intro call/ });
  await expect(firstRow).toContainText(`${firstScore}%`);
  await expect(firstRow).toContainText('100%');
  await expect(firstRow).toContainText(`▲ +${100 - firstScore}`);
  await expect(page.getByRole('heading', { name: 'Feedback so far - attempt 2' })).toBeVisible();

  // A new interview for the same course: both are listed.
  await page.getByRole('link', { name: 'Generate a new interview for this course' }).click();
  await expect(page.getByLabel('Course')).toHaveValue('path:payments-qa-core');
  await page.getByRole('button', { name: 'Generate interview' }).click();
  await expect(page.getByRole('heading', { level: 1, name: / interview$/ })).toBeVisible();
  await page.getByRole('link', { name: 'Interview practice' }).click();
  await expect(page.locator('.interview-list > li')).toHaveCount(2);
});
