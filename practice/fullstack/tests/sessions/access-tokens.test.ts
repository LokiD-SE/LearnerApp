import { decodeJwt, decodeProtectedHeader, SignJWT, UnsecuredJWT } from 'jose';
import { createTokenService, type TokenService } from '../../exercises/sessions/access-tokens.js';

// Test-only key material - obviously not a real secret.
const SECRET = new TextEncoder().encode('test-only-hs256-key-0123456789abcdef!');
const OTHER_SECRET = new TextEncoder().encode('another-test-key-0123456789abcdef-xyz!');
const ISSUER = 'https://auth.sandpay.example';
const AUDIENCE = 'sandpay-dashboard-api';
const T0 = new Date('2026-11-14T10:00:00Z');

function service(clock: { now: Date } = { now: T0 }): TokenService {
  return createTokenService({
    secret: SECRET,
    issuer: ISSUER,
    audience: AUDIENCE,
    accessTtlSeconds: 300,
    now: () => clock.now,
  });
}

const seconds = (date: Date) => Math.floor(date.getTime() / 1000);

/** A token signed with a real key but chosen header and claims - what an attacker or a bug might send. */
async function craft(
  claims: Record<string, unknown>,
  header: { alg: string; typ?: string } = { alg: 'HS256', typ: 'at+jwt' },
  key: Uint8Array = SECRET,
): Promise<string> {
  const base = {
    iss: ISSUER,
    aud: AUDIENCE,
    sub: 'usr_1001',
    roles: ['merchant_admin'],
    iat: seconds(T0),
    exp: seconds(T0) + 300,
    jti: 'at_test_1',
  };
  return new SignJWT({ ...base, ...claims }).setProtectedHeader(header).sign(key);
}

describe('access-tokens', { tags: ['@exercise'] }, () => {
  test('a token it issued verifies, with the user, roles and a token id', async () => {
    const tokens = service();
    const token = await tokens.issueAccessToken('usr_1001', ['merchant_admin']);
    const result = await tokens.verifyAccessToken(token);
    expect(result).toMatchObject({ ok: true, userId: 'usr_1001', roles: ['merchant_admin'] });
    expect(result.ok && result.tokenId.length).toBeGreaterThan(0);
  });

  test('issued tokens are HS256, typed at+jwt, short-lived and unique', async () => {
    const tokens = service();
    const a = await tokens.issueAccessToken('usr_1001', []);
    const b = await tokens.issueAccessToken('usr_1001', []);
    expect(decodeProtectedHeader(a)).toEqual({ alg: 'HS256', typ: 'at+jwt' });
    const claims = decodeJwt(a);
    expect(claims).toMatchObject({ iss: ISSUER, aud: AUDIENCE, sub: 'usr_1001', iat: seconds(T0) });
    expect(claims.exp).toBe(seconds(T0) + 300);
    expect(claims.jti).toBeTypeOf('string');
    expect(decodeJwt(b).jti).not.toBe(claims.jti);
  });

  test('expiry is checked against the injected clock, with 30 seconds of tolerance', async () => {
    const clock = { now: T0 };
    const tokens = service(clock);
    const token = await tokens.issueAccessToken('usr_1001', []);
    clock.now = new Date(T0.getTime() + (300 + 20) * 1000); // 20 s past exp: within tolerance
    expect((await tokens.verifyAccessToken(token)).ok).toBe(true);
    clock.now = new Date(T0.getTime() + (300 + 60) * 1000);
    expect(await tokens.verifyAccessToken(token)).toEqual({ ok: false, reason: 'expired' });
  });

  test('an edited payload fails the signature check', async () => {
    const token = await service().issueAccessToken('usr_1001', ['merchant_viewer']);
    const [header, , signature] = token.split('.');
    const forged = Buffer.from(JSON.stringify({ ...decodeJwt(token), roles: ['platform_admin'] })).toString(
      'base64url',
    );
    expect(await service().verifyAccessToken(`${header}.${forged}.${signature}`)).toEqual({
      ok: false,
      reason: 'invalid',
    });
  });

  test('alg "none" and algorithms outside the allow-list are rejected', async () => {
    const unsigned = new UnsecuredJWT({ sub: 'usr_1001', roles: ['platform_admin'] })
      .setIssuer(ISSUER)
      .setAudience(AUDIENCE)
      .setExpirationTime(seconds(T0) + 300)
      .encode();
    expect(await service().verifyAccessToken(unsigned)).toEqual({ ok: false, reason: 'invalid' });
    const hs512 = await craft({}, { alg: 'HS512', typ: 'at+jwt' }, new Uint8Array(64).fill(7));
    expect(await service().verifyAccessToken(hs512)).toEqual({ ok: false, reason: 'invalid' });
  });

  test('a token signed with a different key is rejected', async () => {
    const token = await craft({}, { alg: 'HS256', typ: 'at+jwt' }, OTHER_SECRET);
    expect(await service().verifyAccessToken(token)).toEqual({ ok: false, reason: 'invalid' });
  });

  test('issuer, audience and type must all match', async () => {
    const tokens = service();
    expect(await tokens.verifyAccessToken(await craft({ iss: 'https://evil.example' }))).toEqual({
      ok: false,
      reason: 'invalid',
    });
    expect(await tokens.verifyAccessToken(await craft({ aud: 'sandpay-admin-api' }))).toEqual({
      ok: false,
      reason: 'invalid',
    });
    // A correctly signed JWT of another kind (an ID token, say) must not pass as an access token.
    expect(await tokens.verifyAccessToken(await craft({}, { alg: 'HS256', typ: 'JWT' }))).toEqual({
      ok: false,
      reason: 'invalid',
    });
  });

  test('tokens without sub, exp or jti are rejected; garbage never throws', async () => {
    const tokens = service();
    for (const missing of ['sub', 'exp', 'jti']) {
      const token = await craft({ [missing]: undefined });
      expect(await tokens.verifyAccessToken(token), `missing ${missing}`).toEqual({
        ok: false,
        reason: 'invalid',
      });
    }
    expect(await tokens.verifyAccessToken('not.a.jwt')).toEqual({ ok: false, reason: 'invalid' });
    expect(await tokens.verifyAccessToken('')).toEqual({ ok: false, reason: 'invalid' });
  });

  test('a secret shorter than 32 bytes is refused when the service is created', () => {
    expect(() =>
      createTokenService({
        secret: new TextEncoder().encode('password123'),
        issuer: ISSUER,
        audience: AUDIENCE,
        accessTtlSeconds: 300,
        now: () => T0,
      }),
    ).toThrow();
  });
});
