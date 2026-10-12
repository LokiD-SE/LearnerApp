// Reference solution. forEach ignores the promises its callback returns, so nothing awaited the checks.
// Promise.allSettled starts them all at once, waits for every one - fulfilled or rejected - and keeps
// the input order in its results.

/**
 * @typedef {{ name: string, run: () => Promise<void> }} Check
 * @typedef {{ passed: string[], failed: { name: string, message: string }[] }} Summary
 */

/**
 * @param {Check[]} checks
 * @returns {Promise<Summary>}
 */
export async function checkAll(checks) {
  const results = await Promise.allSettled(checks.map((check) => check.run()));
  /** @type {Summary} */
  const summary = { passed: [], failed: [] };
  results.forEach((result, index) => {
    const name = /** @type {Check} */ (checks[index]).name;
    if (result.status === 'fulfilled') summary.passed.push(name);
    else {
      const error = result.reason;
      summary.failed.push({ name, message: error instanceof Error ? error.message : String(error) });
    }
  });
  return summary;
}
