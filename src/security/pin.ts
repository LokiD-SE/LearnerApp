/**
 * PIN lock for learner profiles - a separate security layer on top of profiles.ts.
 *
 * Every profile needs a 4-digit PIN to sign in. Built-in PINs are stored only as salted
 * PBKDF2-SHA256 hashes (default 2030; Loki and Gayu have their own). A changed PIN is saved
 * in this browser as a new salted hash under PINS_KEY. A forgotten PIN is reset with the
 * owner's recovery key (its hash only is here); the learner asks for it by email.
 *
 * This is a static site with no server, so the lock keeps people out of each other's profile
 * on a shared device; it is not protection against someone who controls the browser.
 */
import type { KeyValueStore } from '../store/storage';

export const PINS_KEY = 'learnerapp.pins.v1';
export const RECOVERY_EMAIL = 'lokeshdevamuthu@gmail.com';
export const MAX_ATTEMPTS = 5;
export const LOCKOUT_MS = 30_000;
const ITERATIONS = 150_000;

export interface PinHash {
  salt: string;
  hash: string;
}

const DEFAULT_PIN: PinHash = {
  salt: '4a45df8e2f6637bbd77a8fc89c0a5cf2',
  hash: '1072d8d804cedc2377dcd0819d3c444e34c88ec1585087d789b306161f88b5f5',
};
const LOKI_GAYU_PIN: PinHash = {
  salt: '9f8c9c9b57d68ad4dd7cee29bbf7a0a3',
  hash: '7166e505b83eabaf672c9b2ff9e9a0d212e406481446cd1d97bf5a93c9b94549',
};
const RECOVERY_KEY: PinHash = {
  salt: '32b2ec12e4930d0da105a5a170d061c0',
  hash: '42d1069bd135671938082de2438de5dfeb7ebd342ed7494c409f1e245602fd1c',
};
const BUILT_IN: Record<string, PinHash> = { loki: LOKI_GAYU_PIN, gayu: LOKI_GAYU_PIN };

export const isValidPin = (pin: string) => /^\d{4}$/.test(pin);

const hex = (bytes: ArrayBuffer | Uint8Array) =>
  Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
const fromHex = (value: string) => new Uint8Array(value.match(/../g)!.map((h) => parseInt(h, 16)));

export async function hashSecret(secret: string, salt: string): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), 'PBKDF2', false, [
    'deriveBits',
  ]);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: fromHex(salt), iterations: ITERATIONS },
    key,
    256,
  );
  return hex(bits);
}

/** Compares without stopping at the first difference. */
function sameHash(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function savedPins(store: KeyValueStore | undefined): Record<string, PinHash> {
  try {
    const raw = store?.getItem(PINS_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, PinHash>) : {};
  } catch {
    return {};
  }
}

const pinFor = (store: KeyValueStore | undefined, id: string): PinHash =>
  savedPins(store)[id] ?? BUILT_IN[id] ?? DEFAULT_PIN;

export async function verifyPin(store: KeyValueStore | undefined, id: string, pin: string): Promise<boolean> {
  if (!isValidPin(pin)) return false;
  const expected = pinFor(store, id);
  return sameHash(await hashSecret(pin, expected.salt), expected.hash);
}

export async function verifyRecoveryKey(key: string): Promise<boolean> {
  const normalised = key
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
    .replace(/(.{4})(?=.)/g, '$1-');
  return sameHash(await hashSecret(normalised, RECOVERY_KEY.salt), RECOVERY_KEY.hash);
}

/** Saves a new PIN for one profile as a fresh salted hash. */
export async function setPin(store: KeyValueStore | undefined, id: string, pin: string): Promise<boolean> {
  if (!store || !isValidPin(pin)) return false;
  const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
  const pins = { ...savedPins(store), [id]: { salt, hash: await hashSecret(pin, salt) } };
  try {
    store.setItem(PINS_KEY, JSON.stringify(pins));
    return true;
  } catch {
    return false;
  }
}

/** The prefilled email a learner sends to ask for a PIN reset. */
export const resetRequestLink = (firstName: string) =>
  `mailto:${RECOVERY_EMAIL}?subject=${encodeURIComponent(`LearnerApp PIN reset - ${firstName}`)}&body=${encodeURIComponent(
    `Please reset the LearnerApp PIN for the profile "${firstName}".`,
  )}`;
