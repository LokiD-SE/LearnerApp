import {
  SignJWT,
  createLocalJWKSet,
  exportJWK,
  generateKeyPair,
  type CryptoKey,
  type JWTPayload,
} from 'jose';
import {
  OidcError,
  buildAuthorizeUrl,
  createPkcePair,
  readCallback,
  validateIdToken,
  type OidcClientConfig,
} from '../../exercises/auth/oidc-client.js';

const config: OidcClientConfig = {
  issuer: 'https://id.sandpay.example',
  authorizationEndpoint: 'https://id.sandpay.example/authorize',
  clientId: 'merchant-dashboard',
  redirectUri: 'https://dashboard.sandpay.example/auth/callback',
};

// RFC 7636 Appendix B: the 32 octets, the code_verifier and the S256 code_challenge.
const RFC_OCTETS = [
  116, 24, 223, 180, 151, 153, 224, 37, 79, 250, 96, 125, 216, 173, 187, 186, 22, 212, 37, 77, 105, 214, 191,
  240, 91, 88, 5, 88, 83, 132, 141, 121,
];
const RFC_VERIFIER = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
const RFC_CHALLENGE = 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM';

const NOW = new Date('2026-11-14T10:00:00Z');
const nowSeconds = Math.floor(NOW.getTime() / 1000);

let providerKey: CryptoKey;
let attackerKey: CryptoKey;
let keys: ReturnType<typeof createLocalJWKSet>;

beforeAll(async () => {
  const provider = await generateKeyPair('RS256');
  providerKey = provider.privateKey;
  attackerKey = (await generateKeyPair('RS256')).privateKey;
  const jwk = { ...(await exportJWK(provider.publicKey)), kid: 'sandpay-id-1', alg: 'RS256', use: 'sig' };
  keys = createLocalJWKSet({ keys: [jwk] });
});

function idToken(
  claims: JWTPayload = {},
  options: { key?: CryptoKey | Uint8Array; alg?: string; kid?: string } = {},
): Promise<string> {
  return new SignJWT({
    iss: config.issuer,
    aud: config.clientId,
    sub: 'user_8f2c',
    iat: nowSeconds,
    exp: nowSeconds + 300,
    nonce: 'n-0S6_WzA2Mj',
    ...claims,
  })
    .setProtectedHeader({ alg: options.alg ?? 'RS256', kid: options.kid ?? 'sandpay-id-1' })
    .sign(options.key ?? providerKey);
}

const check = () => ({ keys, nonce: 'n-0S6_WzA2Mj', now: NOW });

describe('PKCE and the authorization request', { tags: ['@exercise'] }, () => {
  test('createPkcePair reproduces the RFC 7636 Appendix B example', () => {
    const pair = createPkcePair(() => Buffer.from(RFC_OCTETS));
    expect(pair).toEqual({ verifier: RFC_VERIFIER, challenge: RFC_CHALLENGE, method: 'S256' });
  });

  test('a real verifier is 43 unreserved characters and differs every time', () => {
    const a = createPkcePair();
    const b = createPkcePair();
    expect(a.verifier).toMatch(/^[A-Za-z0-9\-._~]{43}$/);
    expect(a.verifier).not.toBe(b.verifier);
  });

  test('buildAuthorizeUrl asks for a code with openid, state, nonce and an S256 challenge', () => {
    const url = new URL(
      buildAuthorizeUrl(config, {
        state: 'st/1 &x=y',
        nonce: 'n-0S6_WzA2Mj',
        codeChallenge: RFC_CHALLENGE,
        scope: 'email profile',
      }),
    );
    expect(url.origin + url.pathname).toBe(config.authorizationEndpoint);
    const q = url.searchParams;
    expect(q.get('response_type')).toBe('code');
    expect(q.get('client_id')).toBe(config.clientId);
    expect(q.get('redirect_uri')).toBe(config.redirectUri);
    expect(q.get('scope')?.split(' ')).toEqual(expect.arrayContaining(['openid', 'email', 'profile']));
    expect(q.get('state')).toBe('st/1 &x=y');
    expect(q.get('x')).toBeNull();
    expect(q.get('nonce')).toBe('n-0S6_WzA2Mj');
    expect(q.get('code_challenge')).toBe(RFC_CHALLENGE);
    expect(q.get('code_challenge_method')).toBe('S256');
    expect(q.has('code_verifier')).toBe(false);
  });
});

describe('the callback', { tags: ['@exercise'] }, () => {
  const query = (s: string) => new URLSearchParams(s);

  test('returns the code when the state matches', () => {
    expect(readCallback(config, query('code=SplxlOBeZQQYbYS6WxSbIA&state=abc'), 'abc')).toBe(
      'SplxlOBeZQQYbYS6WxSbIA',
    );
    expect(
      readCallback(config, query(`code=c1&state=abc&iss=${encodeURIComponent(config.issuer)}`), 'abc'),
    ).toBe('c1');
  });

  test('rejects a missing or different state - the login CSRF check', () => {
    expect(() => readCallback(config, query('code=c1&state=other'), 'abc')).toThrow(OidcError);
    expect(() => readCallback(config, query('code=c1'), 'abc')).toThrow(OidcError);
    expect(() => readCallback(config, query('code=c1&state='), '')).toThrow(OidcError);
  });

  test('rejects error responses and an iss from another provider', () => {
    expect(() => readCallback(config, query('error=access_denied&state=abc'), 'abc')).toThrow(
      /access_denied/,
    );
    expect(() =>
      readCallback(config, query('code=c1&state=abc&iss=https%3A%2F%2Fevil.example'), 'abc'),
    ).toThrow(OidcError);
  });
});

describe('ID token validation', { tags: ['@exercise'] }, () => {
  test('accepts a token signed by the issuer for this client, and returns its claims', async () => {
    const claims = await validateIdToken(config, await idToken(), check());
    expect(claims.sub).toBe('user_8f2c');
    expect(claims.iss).toBe(config.issuer);
  });

  test('rejects a token signed with someone else key, or edited after signing', async () => {
    await expect(validateIdToken(config, await idToken({}, { key: attackerKey }), check())).rejects.toThrow(
      OidcError,
    );
    const [header, , signature] = (await idToken()).split('.');
    const edited = Buffer.from(
      JSON.stringify({ iss: config.issuer, aud: config.clientId, sub: 'admin' }),
    ).toString('base64url');
    await expect(validateIdToken(config, `${header}.${edited}.${signature}`, check())).rejects.toThrow(
      OidcError,
    );
  });

  test('rejects a symmetric (HS256) token and an unsigned one', async () => {
    const hs = await idToken(
      {},
      { alg: 'HS256', key: new TextEncoder().encode('a-secret-the-attacker-chose-32-b') },
    );
    await expect(validateIdToken(config, hs, check())).rejects.toThrow(OidcError);
    const [, payload] = (await idToken()).split('.');
    const none = `${Buffer.from('{"alg":"none"}').toString('base64url')}.${payload}.`;
    await expect(validateIdToken(config, none, check())).rejects.toThrow(OidcError);
  });

  test('rejects another issuer, another audience, or an extra untrusted audience', async () => {
    await expect(
      validateIdToken(config, await idToken({ iss: 'https://id.sandpay.example/' }), check()),
    ).rejects.toThrow(OidcError);
    await expect(validateIdToken(config, await idToken({ aud: 'reporting-app' }), check())).rejects.toThrow(
      OidcError,
    );
    await expect(
      validateIdToken(config, await idToken({ aud: [config.clientId, 'reporting-app'] }), check()),
    ).rejects.toThrow(OidcError);
  });

  test('rejects an expired token', async () => {
    const expired = await idToken({ iat: nowSeconds - 900, exp: nowSeconds - 600 });
    await expect(validateIdToken(config, expired, check())).rejects.toThrow(OidcError);
  });

  test('rejects a missing or different nonce - the replay and code-injection check', async () => {
    await expect(
      validateIdToken(config, await idToken({ nonce: 'n-from-another-login' }), check()),
    ).rejects.toThrow(/nonce/);
    await expect(validateIdToken(config, await idToken({ nonce: undefined }), check())).rejects.toThrow(
      /nonce/,
    );
  });
});
