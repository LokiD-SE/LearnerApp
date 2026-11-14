import {
  MAX_PASSWORD_LENGTH,
  OWASP_SCRYPT,
  hashPassword,
  needsRehash,
  verifyPassword,
} from '../../exercises/auth/password-hash.js';

// Cheap parameters keep the tests fast; one test checks the OWASP default.
const FAST = { N: 2 ** 10, r: 8, p: 1 };
const PASSWORD = 'correct horse battery staple';

function parts(stored: string) {
  const [algorithm, params, salt, key, ...rest] = stored.split('$');
  return { algorithm, params, salt: salt ?? '', key: key ?? '', rest };
}

describe('password hashing with scrypt', { tags: ['@exercise'] }, () => {
  test('stores the algorithm, its parameters, a 16-byte salt and a 32-byte key', async () => {
    const stored = await hashPassword(PASSWORD, FAST);
    const { algorithm, params, salt, key, rest } = parts(stored);
    expect(algorithm).toBe('scrypt');
    expect(params).toBe('N=1024,r=8,p=1');
    expect(rest).toEqual([]);
    expect(Buffer.from(salt, 'base64url')).toHaveLength(16);
    expect(Buffer.from(key, 'base64url')).toHaveLength(32);
    expect(stored).not.toContain(PASSWORD);
  });

  test('salts every hash: the same password never gives the same string twice', async () => {
    const a = await hashPassword(PASSWORD, FAST);
    const b = await hashPassword(PASSWORD, FAST);
    expect(a).not.toBe(b);
    expect(parts(a).salt).not.toBe(parts(b).salt);
  });

  test('verifies the right password and rejects wrong ones', async () => {
    const stored = await hashPassword(PASSWORD, FAST);
    expect(await verifyPassword(PASSWORD, stored)).toBe(true);
    expect(await verifyPassword('Correct horse battery staple', stored)).toBe(false);
    expect(await verifyPassword(PASSWORD + ' ', stored)).toBe(false);
  });

  test('verifies with the parameters stored in the hash, not the current defaults', async () => {
    const old = await hashPassword(PASSWORD, { N: 2 ** 11, r: 8, p: 2 });
    expect(parts(old).params).toBe('N=2048,r=8,p=2');
    expect(await verifyPassword(PASSWORD, old)).toBe(true);
  });

  test('returns false - never throws - for tampered, truncated or malformed stored values', async () => {
    const stored = await hashPassword(PASSWORD, FAST);
    const { key } = parts(stored);
    const flipped = (key.startsWith('A') ? 'B' : 'A') + key.slice(1);
    const candidates = [
      stored.replace(key, flipped),
      stored.slice(0, -4),
      '',
      'md5$5f4dcc3b5aa765d61d8327deb882cf99',
      'scrypt$N=abc,r=8,p=1$c2FsdA$a2V5',
      'scrypt$N=1000,r=8,p=1$c2FsdA$a2V5',
    ];
    for (const value of candidates) {
      await expect(verifyPassword(PASSWORD, value), value).resolves.toBe(false);
    }
  });

  test('limits the length of what it hashes or verifies', async () => {
    const stored = await hashPassword(PASSWORD, FAST);
    await expect(hashPassword('', FAST)).rejects.toThrow(RangeError);
    await expect(hashPassword('x'.repeat(MAX_PASSWORD_LENGTH + 1), FAST)).rejects.toThrow(RangeError);
    await expect(verifyPassword('x'.repeat(100_000), stored)).resolves.toBe(false);
    const passphrase = 'a long passphrase with spaces and ünïcödé '.repeat(2);
    expect(await verifyPassword(passphrase, await hashPassword(passphrase, FAST))).toBe(true);
  });

  test('defaults to the OWASP parameters and does not block the event loop', async () => {
    let timerRan = false;
    setTimeout(() => (timerRan = true), 0);
    const stored = await hashPassword(PASSWORD);
    expect(parts(stored).params).toBe(`N=${OWASP_SCRYPT.N},r=8,p=1`);
    expect(timerRan, 'a 0 ms timer should run while scrypt works on the thread pool').toBe(true);
    expect(await verifyPassword(PASSWORD, stored)).toBe(true);
  });

  test('needsRehash flags hashes made with weaker parameters or another scheme', async () => {
    const weak = await hashPassword(PASSWORD, FAST);
    expect(needsRehash(weak)).toBe(true);
    expect(needsRehash(weak, FAST)).toBe(false);
    expect(needsRehash(weak, { N: 2 ** 10, r: 8, p: 2 })).toBe(true);
    expect(needsRehash('5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8')).toBe(true);
  });
});
