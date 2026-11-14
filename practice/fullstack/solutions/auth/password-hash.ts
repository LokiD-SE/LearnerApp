// Exercise: store SandPay dashboard passwords with a slow, salted, memory-hard KDF (scrypt), in a
// self-describing string so the cost can be raised later, and verify them in constant time.
// Tests: tests/auth/password-hash.test.ts
import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto';

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

const SALT_BYTES = 16;
const KEY_BYTES = 32;
const FORMAT = /^scrypt\$N=(\d+),r=(\d+),p=(\d+)\$([A-Za-z0-9_-]+)\$([A-Za-z0-9_-]+)$/;

function derive(password: string, salt: Buffer, params: ScryptParams, keyBytes: number): Promise<Buffer> {
  // Node refuses when 128 * N * r exceeds maxmem (32 MiB by default); N=2^17, r=8 needs 128 MiB.
  const maxmem = 256 * params.N * params.r;
  return new Promise((resolve, reject) => {
    scrypt(password.normalize('NFC'), salt, keyBytes, { ...params, maxmem }, (error, key) =>
      error ? reject(error) : resolve(key),
    );
  });
}

/**
 * Hashes a password as `scrypt$N=<N>,r=<r>,p=<p>$<salt>$<hash>` (salt and hash in base64url).
 * A fresh random 16-byte salt every time; the work runs on libuv's thread pool, not the event loop.
 */
export async function hashPassword(password: string, params: ScryptParams = OWASP_SCRYPT): Promise<string> {
  if (password.length === 0 || password.length > MAX_PASSWORD_LENGTH) {
    throw new RangeError(`password must be 1-${MAX_PASSWORD_LENGTH} characters`);
  }
  const salt = randomBytes(SALT_BYTES);
  const key = await derive(password, salt, params, KEY_BYTES);
  return `scrypt$N=${params.N},r=${params.r},p=${params.p}$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

function parse(stored: string): { params: ScryptParams; salt: Buffer; key: Buffer } | undefined {
  const match = FORMAT.exec(stored);
  if (!match) return undefined;
  const [, n, r, p, salt, key] = match;
  const params = { N: Number(n), r: Number(r), p: Number(p) };
  if (!Number.isSafeInteger(params.N) || params.N < 2 || (params.N & (params.N - 1)) !== 0) return undefined;
  if (params.r < 1 || params.p < 1) return undefined;
  return { params, salt: Buffer.from(salt!, 'base64url'), key: Buffer.from(key!, 'base64url') };
}

/**
 * True only if `password` produces the stored hash. Never throws for a bad password or a malformed or
 * tampered stored value - it returns false. Uses the parameters stored in the hash, and compares in
 * constant time.
 */
export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  if (password.length === 0 || password.length > MAX_PASSWORD_LENGTH) return false;
  const parsed = parse(stored);
  if (!parsed || parsed.key.length !== KEY_BYTES) return false;
  try {
    const candidate = await derive(password, parsed.salt, parsed.params, parsed.key.length);
    return timingSafeEqual(candidate, parsed.key);
  } catch {
    return false;
  }
}

/** True when the stored hash isn't scrypt in this format, or any of its parameters is below `params`. */
export function needsRehash(stored: string, params: ScryptParams = OWASP_SCRYPT): boolean {
  const parsed = parse(stored);
  if (!parsed) return true;
  return parsed.params.N < params.N || parsed.params.r < params.r || parsed.params.p < params.p;
}
