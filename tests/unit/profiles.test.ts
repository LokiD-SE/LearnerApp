import { describe, expect, it } from 'vitest';
import {
  NAME_RULE_ERROR,
  PROFILES_KEY,
  addProfile,
  defaultProfiles,
  loadProfiles,
  progressKey,
  progressPercentage,
  signIn,
  signOut,
  validateFirstName,
  withSummary,
} from '../../src/store/profiles';
import { STORAGE_KEY } from '../../src/store/storage';
import { at, memoryStore } from './helpers';

describe('profiles', () => {
  it('a fresh browser gets the five default profiles, nobody signed in, and saves them', () => {
    const store = memoryStore();
    const { state, warning } = loadProfiles(store);
    expect(warning).toBeUndefined();
    expect(state.activeUserId).toBeNull();
    expect(Object.values(state.profiles).map((p) => p.firstName)).toEqual([
      'Loki',
      'Gayu',
      'Kishore',
      'Saurabh',
      'Raji',
    ]);
    expect(state.profiles.loki).toEqual({
      firstName: 'Loki',
      completedLessons: [],
      lastActiveLesson: null,
      progressPercentage: 0,
    });
    expect(JSON.parse(store.data[PROFILES_KEY]!)).toEqual(state);
  });

  it('copies progress saved before profiles existed to Loki, once', () => {
    const store = memoryStore({ [STORAGE_KEY]: '{"old":true}' });
    loadProfiles(store);
    expect(store.data[progressKey('loki')]).toBe('{"old":true}');
    expect(store.data[progressKey('gayu')]).toBeUndefined();

    // Later loads find the profile list and leave Loki's own progress alone.
    store.data[progressKey('loki')] = '{"new":true}';
    loadProfiles(store);
    expect(store.data[progressKey('loki')]).toBe('{"new":true}');
  });

  it('keeps the signed-in profile across loads, and forgets one that no longer exists', () => {
    const store = memoryStore();
    store.data[PROFILES_KEY] = JSON.stringify(signIn(defaultProfiles(), 'raji'));
    expect(loadProfiles(store).state.activeUserId).toBe('raji');
    store.data[PROFILES_KEY] = JSON.stringify({ ...defaultProfiles(), activeUserId: 'ghost' });
    expect(loadProfiles(store).state.activeUserId).toBeNull();
  });

  it('a corrupt profile list is kept aside and the defaults restored', () => {
    const store = memoryStore({ [PROFILES_KEY]: '{broken' });
    const { state, warning } = loadProfiles(store, at('2026-10-29T10:00:00.000Z'));
    expect(state).toEqual(defaultProfiles());
    expect(warning).toContain('could not be read');
    expect(store.data['learnerapp.profiles.corrupt.2026-10-29T10:00:00.000Z']).toBe('{broken');
  });

  it('works without storage', () => {
    expect(loadProfiles(undefined).state).toEqual(defaultProfiles());
  });

  it('a new name is trimmed, one word of letters, capitalised and unique', () => {
    const state = defaultProfiles();
    expect(validateFirstName('  priya ', state)).toEqual({ ok: true, firstName: 'Priya', id: 'priya' });
    expect(validateFirstName('Mary Ann', state)).toEqual({ ok: false, error: NAME_RULE_ERROR });
    expect(validateFirstName('o-neil', state)).toEqual({ ok: false, error: NAME_RULE_ERROR });
    expect(validateFirstName('R2D2', state)).toEqual({ ok: false, error: NAME_RULE_ERROR });
    expect(validateFirstName('   ', state).ok).toBe(false);
    expect(validateFirstName('a'.repeat(31), state).ok).toBe(false);
    expect(validateFirstName('LOKI', state)).toEqual({
      ok: false,
      error: 'There is already a profile called Loki',
    });
    expect(validateFirstName('அருண்', state).ok).toBe(true);
  });

  it('adding signs the new profile in; switching signs out', () => {
    const added = addProfile(defaultProfiles(), 'Priya');
    expect(added.activeUserId).toBe('priya');
    expect(added.profiles.priya?.completedLessons).toEqual([]);
    expect(signOut(added).activeUserId).toBeNull();
    expect(signIn(added, 'nobody')).toBe(added);
  });

  it('stores a summary only when it changed', () => {
    const state = signIn(defaultProfiles(), 'gayu');
    const summary = { completedLessons: ['a', 'b'], lastActiveLesson: 'b', progressPercentage: 3 };
    const next = withSummary(state, 'gayu', summary);
    expect(next.profiles.gayu).toMatchObject(summary);
    expect(next.profiles.loki).toEqual(state.profiles.loki);
    expect(withSummary(next, 'gayu', { ...summary, completedLessons: ['a', 'b'] })).toBe(next);
  });

  it('progress percentage is completed over total, rounded', () => {
    expect(progressPercentage(0, 67)).toBe(0);
    expect(progressPercentage(1, 3)).toBe(33);
    expect(progressPercentage(67, 67)).toBe(100);
    expect(progressPercentage(0, 0)).toBe(0);
  });
});
