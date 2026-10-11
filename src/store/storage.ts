/**
 * Persistence: progress lives in this browser's localStorage under one key. Loading never
 * throws - an unreadable or unavailable store falls back to an empty state with a warning
 * the UI shows, and a corrupt value is kept aside instead of being overwritten.
 */
import { ProgressStateSchema, STATE_VERSION, emptyState, type ProgressState } from './state';

export const STORAGE_KEY = 'learnerapp.progress.v1';
export const CORRUPT_PREFIX = 'learnerapp.progress.corrupt.';

/** The subset of the Web Storage API we use; tests pass an in-memory implementation. */
export type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

export interface LoadResult {
  state: ProgressState;
  /** Set when progress could not be read; shown to the learner. */
  warning?: string;
  /** False when the store cannot be written at all (e.g. storage disabled). */
  persistent: boolean;
}

export function browserStore(): KeyValueStore | undefined {
  try {
    const store = globalThis.localStorage;
    const probe = '__learnerapp_probe__';
    store.setItem(probe, '1');
    store.removeItem(probe);
    return store;
  } catch {
    return undefined;
  }
}

export function parseProgress(
  text: string,
): { ok: true; state: ProgressState } | { ok: false; error: string } {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    return { ok: false, error: 'not valid JSON' };
  }
  if (typeof json === 'object' && json !== null && 'version' in json && json.version !== STATE_VERSION) {
    // Future schema versions add a migration step here.
    return { ok: false, error: `unsupported progress version ${String(json.version)}` };
  }
  const parsed = ProgressStateSchema.safeParse(json);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    return {
      ok: false,
      error: `unexpected data at ${issue?.path.join('.') || '(root)'}: ${issue?.message ?? 'invalid'}`,
    };
  }
  return { ok: true, state: parsed.data };
}

export function loadProgress(store: KeyValueStore | undefined, now: Date = new Date()): LoadResult {
  if (!store) {
    return {
      state: emptyState(),
      persistent: false,
      warning:
        'This browser is not letting LearnerApp save data (storage is disabled or full). Progress will be lost when you close the page.',
    };
  }
  let raw: string | null;
  try {
    raw = store.getItem(STORAGE_KEY);
  } catch {
    return {
      state: emptyState(),
      persistent: false,
      warning: 'Saved progress could not be read from this browser.',
    };
  }
  if (raw === null) return { state: emptyState(), persistent: true };

  const parsed = parseProgress(raw);
  if (parsed.ok) return { state: parsed.state, persistent: true };

  const backupKey = `${CORRUPT_PREFIX}${now.toISOString()}`;
  try {
    store.setItem(backupKey, raw);
  } catch {
    // Nothing more we can do; the warning still tells the learner.
  }
  return {
    state: emptyState(),
    persistent: true,
    warning: `Saved progress could not be loaded (${parsed.error}). It was kept in this browser as "${backupKey}" and a fresh start was made.`,
  };
}

export function saveProgress(
  store: KeyValueStore | undefined,
  state: ProgressState,
): { ok: true } | { ok: false; error: string } {
  if (!store) return { ok: false, error: 'storage unavailable' };
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(state));
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}

export const exportProgress = (state: ProgressState) => JSON.stringify(state, null, 2);
