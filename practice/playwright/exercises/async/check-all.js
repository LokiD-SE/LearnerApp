// Exercise - running async checks without losing them. (Plain JavaScript; the types are JSDoc comments.)
//
// Lesson: "JavaScript and TypeScript for testers". Tests: tests/check-all.spec.ts
// Run: npx playwright test tests/check-all.spec.ts
//
// checkAll returns before any check has finished, so the summary is always empty. Fix it.

/**
 * @typedef {{ name: string, run: () => Promise<void> }} Check
 * @typedef {{ passed: string[], failed: { name: string, message: string }[] }} Summary
 */

/**
 * Runs every check at the same time and reports which passed and which failed - both lists in the
 * order of `checks`, not the order they finished. A failing check (a rejected promise) must not stop
 * the others.
 *
 * @param {Check[]} checks
 * @returns {Promise<Summary>}
 */
export async function checkAll(checks) {
  /** @type {Summary} */
  const summary = { passed: [], failed: [] };
  checks.forEach(async (check) => {
    try {
      await check.run();
      summary.passed.push(check.name);
    } catch (error) {
      summary.failed.push({
        name: check.name,
        message: error instanceof Error ? error.message : String(error),
      });
    }
  });
  return summary;
}
