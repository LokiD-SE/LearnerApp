// Exercise: the client side of "Sign in with SandPay ID" - OpenID Connect's authorization code flow
// with PKCE: build the authorization request, check the callback, and validate the ID token.
// Tests: tests/auth/oidc-client.test.ts
//
// A teammate's first draft, copied from a blog post. Each function has at least one gap an attacker
// can use. Fix them, keeping the exported names and signatures.
import { createHash, randomBytes } from 'node:crypto';
import { decodeJwt, type JWTPayload, type JWTVerifyGetKey } from 'jose';

export interface OidcClientConfig {
  /** The provider's Issuer Identifier - exactly as in its discovery document and its ID tokens. */
  issuer: string;
  authorizationEndpoint: string;
  clientId: string;
  /** Registered with the provider; the provider compares it by exact string match (RFC 9700). */
  redirectUri: string;
}

export interface PkcePair {
  verifier: string;
  challenge: string;
  method: 'S256';
}

/** Thrown for any callback or ID token that must not sign anyone in. */
export class OidcError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'OidcError';
  }
}

/**
 * Should follow RFC 7636: a code_verifier from 32 random octets, base64url-encoded (43 characters),
 * and its S256 code_challenge = BASE64URL(SHA256(ASCII(code_verifier))). `random` is injectable for tests.
 */
export function createPkcePair(random: (size: number) => Buffer = randomBytes): PkcePair {
  const verifier = random(32).toString('hex');
  const challenge = createHash('sha256').update(verifier).digest('base64');
  return { verifier, challenge, method: 'S256' };
}

/** Should build the URL to send the browser to: an authorization code request for the openid scope, with PKCE. */
export function buildAuthorizeUrl(
  config: OidcClientConfig,
  request: { state: string; nonce: string; codeChallenge: string; scope?: string },
): string {
  return (
    `${config.authorizationEndpoint}?response_type=code&client_id=${config.clientId}` +
    `&redirect_uri=${config.redirectUri}&scope=${request.scope ?? 'profile'}&state=${request.state}`
  );
}

/**
 * Should check the redirect back to the client and return the authorization code, rejecting error
 * responses, a state that isn't the one stored for this browser, a missing code, and an `iss`
 * parameter (RFC 9207) that names another issuer.
 */
export function readCallback(
  config: OidcClientConfig,
  query: URLSearchParams,
  expectedState: string,
): string {
  void config;
  void expectedState;
  const code = query.get('code');
  if (!code) throw new OidcError('no authorization code');
  return code;
}

export interface IdTokenCheck {
  /** The provider's signing keys, e.g. createRemoteJWKSet(jwks_uri) - or a local set in tests. */
  keys: JWTVerifyGetKey;
  /** The nonce sent in this browser's authorization request. */
  nonce: string;
  /** Algorithms this client accepts. */
  algorithms?: string[];
  /** "Now", for tests. */
  now?: Date;
}

/**
 * Should follow OpenID Connect Core 1.0 section 3.1.3.7: verify the signature with the issuer's keys
 * and an allowed algorithm, iss exactly equal to the issuer, aud containing this client and no other
 * audience, exp in the future, and the nonce equal to the one sent. Returns the verified claims.
 */
export async function validateIdToken(
  config: OidcClientConfig,
  idToken: string,
  check: IdTokenCheck,
): Promise<JWTPayload & { sub: string }> {
  const payload = decodeJwt(idToken);
  if (payload.aud !== config.clientId && !(payload.aud ?? []).includes(config.clientId)) {
    throw new OidcError('wrong audience');
  }
  void check;
  return payload as JWTPayload & { sub: string };
}
