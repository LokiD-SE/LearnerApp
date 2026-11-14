// Exercise: short-lived access tokens for the SandPay dashboard API (fictional), signed and checked
// with jose. Tests: tests/sessions/access-tokens.test.ts

import { randomUUID } from 'node:crypto';
import { errors, jwtVerify, SignJWT } from 'jose';

export interface TokenServiceOptions {
  /** The HS256 key: at least 32 random bytes (256 bits). Never a password or a short string. */
  secret: Uint8Array;
  /** Who issues the tokens - the "iss" claim, e.g. https://auth.sandpay.example */
  issuer: string;
  /** Which API the tokens are for - the "aud" claim, e.g. sandpay-dashboard-api */
  audience: string;
  /** Lifetime of an access token in seconds - keep it short (minutes). */
  accessTtlSeconds: number;
  /** The current time. Tests pass a fake clock. */
  now(): Date;
}

export type VerifiedAccess =
  | { ok: true; userId: string; roles: string[]; tokenId: string }
  | { ok: false; reason: 'expired' | 'invalid' };

export interface TokenService {
  issueAccessToken(userId: string, roles: string[]): Promise<string>;
  verifyAccessToken(token: string): Promise<VerifiedAccess>;
}

/** The only algorithm this service signs with - and so the only one it accepts (RFC 8725 3.1). */
const ALGORITHM = 'HS256';
/** Explicit typing (RFC 8725 3.11, RFC 9068): an ID token or some other JWT can't pass as an access token. */
const TOKEN_TYPE = 'at+jwt';
/** Allowance for clocks that disagree a little between servers. */
const CLOCK_TOLERANCE_SECONDS = 30;

export function createTokenService(options: TokenServiceOptions): TokenService {
  // jose signs happily with a 5-byte HS256 key, so the size check is ours to make.
  if (options.secret.byteLength < 32) {
    throw new Error('HS256 secret must be at least 32 bytes (256 bits) of random data');
  }

  return {
    async issueAccessToken(userId, roles) {
      const iat = Math.floor(options.now().getTime() / 1000);
      return new SignJWT({ roles })
        .setProtectedHeader({ alg: ALGORITHM, typ: TOKEN_TYPE })
        .setIssuer(options.issuer)
        .setAudience(options.audience)
        .setSubject(userId)
        .setIssuedAt(iat)
        .setExpirationTime(iat + options.accessTtlSeconds)
        .setJti(randomUUID())
        .sign(options.secret);
    },

    async verifyAccessToken(token) {
      try {
        const { payload } = await jwtVerify(token, options.secret, {
          algorithms: [ALGORITHM],
          issuer: options.issuer,
          audience: options.audience,
          typ: TOKEN_TYPE,
          clockTolerance: CLOCK_TOLERANCE_SECONDS,
          currentDate: options.now(),
          requiredClaims: ['sub', 'exp', 'iat', 'jti'],
        });
        const roles = payload.roles;
        if (
          typeof payload.sub !== 'string' ||
          typeof payload.jti !== 'string' ||
          !Array.isArray(roles) ||
          !roles.every((r): r is string => typeof r === 'string')
        ) {
          return { ok: false, reason: 'invalid' };
        }
        return { ok: true, userId: payload.sub, roles, tokenId: payload.jti };
      } catch (err) {
        // Only the expiry is worth telling apart (the client should refresh). Everything else -
        // bad signature, wrong alg, issuer, audience, type, malformed token - is just "invalid".
        if (err instanceof errors.JWTExpired) return { ok: false, reason: 'expired' };
        if (err instanceof errors.JOSEError) return { ok: false, reason: 'invalid' };
        throw err;
      }
    },
  };
}
