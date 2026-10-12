// Exercise - a typed, async polling helper.
//
// Lesson: "JavaScript and TypeScript for testers". Tests: tests/poll-until.spec.ts
// Run: npx playwright test tests/poll-until.spec.ts
//
// The helper below sleeps for the whole timeout and reads once - slow when the value is ready early,
// and wrong when it isn't. Rewrite it so it asks repeatedly.

export interface PollOptions {
  /** Give up after this many milliseconds. */
  timeout: number;
  /** Wait this long between calls. */
  interval: number;
}

/**
 * Calls `read` until `isDone(value)` is true and resolves with that value. Waits `interval` ms between
 * calls, and never calls `read` again before the previous call has finished. Rejects with an Error whose
 * message contains "timed out" and the last value read if `timeout` ms pass first.
 */
export async function pollUntil<T>(
  read: () => Promise<T>,
  isDone: (value: T) => boolean,
  options: PollOptions,
): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, options.timeout));
  return read();
}
