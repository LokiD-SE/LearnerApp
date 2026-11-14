// Exercise: the client side of "Sign in with SandPay ID" - OpenID Connect's authorization code flow
// with PKCE: build the authorization request, check the callback, and validate the ID token.
// Tests: tests/auth/oidc-client.test.ts
import { createHash, randomBytes } from 'node:crypto';
import { jwtVerify, type JWTPayload, type JWTVerifyGetKey } from 'jose';

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
 * RFC 7636: a code_verifier from 32 random octets, base64url-encoded (43 characters), and its S256
 * code_challenge = BASE64URL(SHA256(ASCII(code_verifier))). `random` is injectable for tests.
 */
export function createPkcePair(random: (size: number) => Buffer = randomBytes): PkcePair {
  const verifier = random(32).toString('base64url');
  const challenge = createHash('sha256').update(verifier, 'ascii').digest('base64url');
  return { verifier, challenge, method: 'S256' };
}

/** The URL to send the browser to: an authorization code request for the openid scope, with PKCE. */
export function buildAuthorizeUrl(
  config: OidcClientConfig,
  request: { state: string; nonce: string; codeChallenge: string; scope?: string },
): string {
  const scopes = new Set(['openid', ...(request.scope ?? '').split(' ').filter(Boolean)]);
  const url = new URL(config.authorizationEndpoint);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('client_id', config.clientId);
  url.searchParams.set('redirect_uri', config.redirectUri);
  url.searchParams.set('scope', [...scopes].join(' '));
  url.searchParams.set('state', request.state);
  url.searchParams.set('nonce', request.nonce);
  url.searchParams.set('code_challenge', request.codeChallenge);
  url.searchParams.set('code_challenge_method', 'S256');
  return url.toString();
}

/**
 * Checks the redirect back to the client and returns the authorization code. Rejects error
 * responses, a state that isn't the one stored for this browser, a missing code, and an `iss`
 * parameter (RFC 9207) that names another issuer.
 */
export function readCallback(
  config: OidcClientConfig,
  query: URLSearchParams,
  expectedState: string,
): string {
  const error = query.get('error');
  if (error) throw new OidcError(`provider returned error: ${error}`);
  if (!expectedState || query.get('state') !== expectedState) throw new OidcError('state does not match');
  const iss = query.get('iss');
  if (iss !== null && iss !== config.issuer) throw new OidcError('iss does not match the expected issuer');
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
 * OpenID Connect Core 1.0 section 3.1.3.7: verify the signature with the issuer's keys and an allowed
 * algorithm, iss exactly equal to the issuer, aud containing this client and no other audience,
 * exp in the future, and the nonce equal to the one sent. Returns the verified claims.
 */
export async function validateIdToken(
  config: OidcClientConfig,
  idToken: string,
  check: IdTokenCheck,
): Promise<JWTPayload & { sub: string }> {
  let payload: JWTPayload;
  try {
    ({ payload } = await jwtVerify(idToken, check.keys, {
      issuer: config.issuer,
      audience: config.clientId,
      algorithms: check.algorithms ?? ['RS256', 'ES256'],
      requiredClaims: ['sub', 'exp', 'iat'],
      currentDate: check.now,
    }));
  } catch (error) {
    throw new OidcError(`ID token rejected: ${(error as Error).message}`);
  }
  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (audiences.some((aud) => aud !== config.clientId))
    throw new OidcError('ID token has an untrusted audience');
  if (!check.nonce || payload.nonce !== check.nonce) throw new OidcError('nonce does not match');
  return payload as JWTPayload & { sub: string };
}
