// Exercise: store SandPay dashboard passwords with a slow, salted, memory-hard KDF (scrypt), in a
// self-describing string so the cost can be raised later, and verify them in constant time.
// Tests: tests/auth/password-hash.test.ts
//
// This is the first sprint's version. It "works" - and a stolen database would give up most
// passwords in an afternoon. Replace it, keeping the exported names and signatures.
import { createHash } from 'node:crypto';

/** scrypt's three cost parameters: CPU/memory cost N (a power of two), block size r, parallelism p. */
export interface ScryptParams {
  N: number;
  r: number;
  p: number;
}

/** OWASP Password Storage Cheat Sheet: "N=2^17 (128 MiB), r=8 (1024 bytes), p=1". */
export const OWASP_SCRYPT: ScryptParams = { N: 2 ** 17, r: 8, p: 1 };

/** Longest password accepted, in characters - long enough for any passphrase, short enough to stop abuse. */
export const MAX_PASSWORD_LENGTH = 1024;

/**
 * Should hash a password as `scrypt$N=<N>,r=<r>,p=<p>$<salt>$<hash>` (salt and hash in base64url),
 * with a fresh random 16-byte salt every time and a 32-byte key, without blocking the event loop.
 * Throws a RangeError for an empty password or one longer than MAX_PASSWORD_LENGTH.
 */
export async function hashPassword(password: string, params: ScryptParams = OWASP_SCRYPT): Promise<string> {
  void params;
  return createHash('sha256').update(password).digest('hex');
}

/**
 * Should be true only if `password` produces the stored hash. Never throws for a bad password or a
 * malformed or tampered stored value - it returns false. Uses the parameters stored in the hash, and
 * compares in constant time.
 */
export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  return createHash('sha256').update(password).digest('hex') === stored;
}

/** Should be true when the stored hash isn't scrypt in this format, or any of its parameters is below `params`. */
export function needsRehash(stored: string, params: ScryptParams = OWASP_SCRYPT): boolean {
  void stored;
  void params;
  return false;
}
