/**
 * Learner profiles on a shared device: who is studying now, and a summary of each profile's
 * progress. There is no password - picking a profile signs in. Each profile's full progress
 * (a ProgressState) lives under its own localStorage key, so profiles never see each other's
 * data; the registry here keeps only the summary shown on the profile screen.
 *
 * Everything except loadProfiles / saveProfiles is pure and unit-tested without a browser.
 */
import { z } from 'zod';
import { STORAGE_KEY, type KeyValueStore } from './storage';

export const PROFILES_KEY = 'learnerapp.profiles.v1';
export const PROFILES_CORRUPT_PREFIX = 'learnerapp.profiles.corrupt.';
export const DEFAULT_PROFILES = ['Loki', 'Gayu', 'Kishore', 'Saurabh', 'Raji'] as const;
/** The profile that inherits progress saved before profiles existed. */
export const LEGACY_PROFILE_ID = 'loki';
export const MAX_NAME_LENGTH = 30;
export const NAME_RULE_ERROR = 'Please enter a single-word first name with no spaces';

/** Where a profile's full progress is stored; ids are the lower-cased first name (see validateFirstName). */
export const progressKey = (profileId: string) => `learnerapp.profile.${profileId}.progress.v1`;

const ProfileSchema = z.object({
  firstName: z.string().min(1),
  /** ids of published lessons that are completed or mastered */
  completedLessons: z.array(z.string()).default([]),
  lastActiveLesson: z.string().nullable().default(null),
  /** completed lessons / published lessons * 100, rounded */
  progressPercentage: z.number().min(0).max(100).default(0),
});

export const ProfilesStateSchema = z.object({
  activeUserId: z.string().nullable().default(null),
  profiles: z.record(z.string(), ProfileSchema),
});

export type Profile = z.infer<typeof ProfileSchema>;
export type ProfilesState = z.infer<typeof ProfilesStateSchema>;
export type ProfileSummary = Pick<Profile, 'completedLessons' | 'lastActiveLesson' | 'progressPercentage'>;

const newProfile = (firstName: string): Profile => ({
  firstName,
  completedLessons: [],
  lastActiveLesson: null,
  progressPercentage: 0,
});

export const profileId = (firstName: string) => firstName.toLowerCase();

export const defaultProfiles = (): ProfilesState => ({
  activeUserId: null,
  profiles: Object.fromEntries(DEFAULT_PROFILES.map((name) => [profileId(name), newProfile(name)])),
});

/**
 * A new profile's name: trimmed, one word of letters only, first letter capitalised.
 * Letters of any script (with their combining marks, as in Tamil) are allowed.
 */
export function validateFirstName(
  input: string,
  existing: ProfilesState,
): { ok: true; firstName: string; id: string } | { ok: false; error: string } {
  const trimmed = input.trim();
  if (trimmed === '') return { ok: false, error: 'Please enter a first name' };
  if (!/^\p{L}[\p{L}\p{M}]*$/u.test(trimmed)) return { ok: false, error: NAME_RULE_ERROR };
  if (trimmed.length > MAX_NAME_LENGTH) {
    return { ok: false, error: `Please keep the name to ${MAX_NAME_LENGTH} letters or fewer` };
  }
  const firstName = trimmed.charAt(0).toLocaleUpperCase() + trimmed.slice(1);
  const id = profileId(firstName);
  if (existing.profiles[id]) {
    return { ok: false, error: `There is already a profile called ${existing.profiles[id].firstName}` };
  }
  return { ok: true, firstName, id };
}

/** Adds a profile and signs it in. The name must already have passed validateFirstName. */
export function addProfile(state: ProfilesState, firstName: string): ProfilesState {
  const id = profileId(firstName);
  return { activeUserId: id, profiles: { ...state.profiles, [id]: newProfile(firstName) } };
}

export function signIn(state: ProfilesState, id: string): ProfilesState {
  return state.profiles[id] ? { ...state, activeUserId: id } : state;
}

export const signOut = (state: ProfilesState): ProfilesState => ({ ...state, activeUserId: null });

/** Stores a profile's latest summary; returns the same object when nothing changed. */
export function withSummary(state: ProfilesState, id: string, summary: ProfileSummary): ProfilesState {
  const current = state.profiles[id];
  if (!current) return state;
  const same =
    current.lastActiveLesson === summary.lastActiveLesson &&
    current.progressPercentage === summary.progressPercentage &&
    current.completedLessons.length === summary.completedLessons.length &&
    current.completedLessons.every((lesson, i) => lesson === summary.completedLessons[i]);
  if (same) return state;
  return { ...state, profiles: { ...state.profiles, [id]: { ...current, ...summary } } };
}

export const progressPercentage = (completed: number, total: number) =>
  total > 0 ? Math.round((completed / total) * 100) : 0;

export interface ProfilesLoad {
  state: ProfilesState;
  /** Set when the saved profiles could not be read; shown to the learner. */
  warning?: string;
}

/**
 * Reads the profiles, creating the five default profiles on a fresh browser. Progress saved
 * before profiles existed is copied to Loki's profile the first time, so it is not lost.
 */
export function loadProfiles(store: KeyValueStore | undefined, now: Date = new Date()): ProfilesLoad {
  if (!store) return { state: defaultProfiles() };
  let raw: string | null;
  try {
    raw = store.getItem(PROFILES_KEY);
  } catch {
    return { state: defaultProfiles() };
  }

  if (raw === null) {
    const state = defaultProfiles();
    try {
      const legacy = store.getItem(STORAGE_KEY);
      if (legacy !== null && store.getItem(progressKey(LEGACY_PROFILE_ID)) === null) {
        store.setItem(progressKey(LEGACY_PROFILE_ID), legacy);
      }
    } catch {
      // The legacy progress stays where it was; nothing is lost.
    }
    saveProfiles(store, state);
    return { state };
  }

  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    json = undefined;
  }
  const parsed = ProfilesStateSchema.safeParse(json);
  if (parsed.success) {
    const state = parsed.data;
    // A signed-in profile that no longer exists means nobody is signed in.
    if (state.activeUserId !== null && !state.profiles[state.activeUserId]) state.activeUserId = null;
    return { state };
  }

  const backupKey = `${PROFILES_CORRUPT_PREFIX}${now.toISOString()}`;
  try {
    store.setItem(backupKey, raw);
  } catch {
    // The warning still tells the learner.
  }
  const state = defaultProfiles();
  saveProfiles(store, state);
  return {
    state,
    warning: `The saved profile list could not be read, so the default profiles were restored. The old list was kept in this browser as "${backupKey}"; each profile's progress is stored separately and was not touched.`,
  };
}

export function saveProfiles(store: KeyValueStore | undefined, state: ProfilesState): boolean {
  if (!store) return false;
  try {
    store.setItem(PROFILES_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
