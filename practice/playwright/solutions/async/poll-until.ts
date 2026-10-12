// Reference solution - a loop with await: one call at a time, a pause between calls, and a deadline.
// The type parameter T flows from read to isDone to the result, so callers keep their types.

export interface PollOptions {
  timeout: number;
  interval: number;
}

export async function pollUntil<T>(
  read: () => Promise<T>,
  isDone: (value: T) => boolean,
  options: PollOptions,
): Promise<T> {
  const deadline = Date.now() + options.timeout;
  for (;;) {
    const value = await read();
    if (isDone(value)) return value;
    if (Date.now() + options.interval > deadline) {
      throw new Error(
        `pollUntil timed out after ${options.timeout} ms; last value: ${JSON.stringify(value)}`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, options.interval));
  }
}
