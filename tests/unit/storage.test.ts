import { describe, expect, it } from 'vitest';
import { emptyState, recordAttempt, markRead } from '../../src/store/state';
import {
  CORRUPT_PREFIX,
  STORAGE_KEY,
  exportProgress,
  loadProgress,
  parseProgress,
  saveProgress,
} from '../../src/store/storage';
import { at, memoryStore, realIndex } from './helpers';

const lesson = realIndex().lessons.get('idempotency-keys')!;
const now = at('2026-10-01T09:00:00.000Z');

describe('progress persistence', () => {
  it('starts empty and persistent when nothing is stored', () => {
    const result = loadProgress(memoryStore(), now);
    expect(result).toEqual({ state: emptyState(), persistent: true });
  });

  it('round-trips a real state through the store', () => {
    const store = memoryStore();
    let state = markRead(emptyState(), lesson, now);
    state = recordAttempt(
      state,
      {
        lesson,
        itemId: 'methods-idempotent',
        kind: 'exercise',
        concept: 'idempotent-operations',
        skill: 'recognition',
        score: 1,
        hintsUsed: 1,
        selfAssessed: false,
        firstTry: true,
        mode: 'lesson',
        response: 'get, put, delete',
      },
      now,
    );
    expect(saveProgress(store, state)).toEqual({ ok: true });
    const loaded = loadProgress(store, now);
    expect(loaded.warning).toBeUndefined();
    expect(loaded.state).toEqual(state);
  });

  it('keeps corrupt data aside and starts fresh with a warning', () => {
    const store = memoryStore({ [STORAGE_KEY]: '{not json' });
    const result = loadProgress(store, now);
    expect(result.state).toEqual(emptyState());
    expect(result.warning).toMatch(/could not be loaded/);
    expect(store.data[`${CORRUPT_PREFIX}${now.toISOString()}`]).toBe('{not json');
  });

  it('rejects data with the wrong shape', () => {
    const bad = JSON.stringify({ version: 1, attempts: [{ score: 7 }] });
    const result = loadProgress(memoryStore({ [STORAGE_KEY]: bad }), now);
    expect(result.warning).toMatch(/unexpected data at attempts/);
  });

  it('rejects an unknown version instead of misreading it', () => {
    expect(parseProgress(JSON.stringify({ version: 99 }))).toEqual({
      ok: false,
      error: 'unsupported progress version 99',
    });
  });

  it('works without storage, and says so', () => {
    const result = loadProgress(undefined, now);
    expect(result.persistent).toBe(false);
    expect(result.warning).toMatch(/not letting LearnerApp save/);
    expect(saveProgress(undefined, emptyState())).toEqual({ ok: false, error: 'storage unavailable' });
  });

  it('reports a failed write (e.g. quota exceeded) instead of throwing', () => {
    const store = {
      getItem: () => null,
      setItem: () => {
        throw new Error('QuotaExceededError');
      },
    };
    expect(saveProgress(store, emptyState())).toEqual({ ok: false, error: 'QuotaExceededError' });
  });

  it('a read that throws falls back to an empty, non-persistent state', () => {
    const store = {
      getItem: () => {
        throw new Error('SecurityError');
      },
      setItem: () => undefined,
    };
    const result = loadProgress(store, now);
    expect(result.persistent).toBe(false);
    expect(result.state).toEqual(emptyState());
  });

  it('exported progress imports back unchanged', () => {
    const state = markRead(emptyState(), lesson, now);
    expect(parseProgress(exportProgress(state))).toEqual({ ok: true, state });
  });
});
