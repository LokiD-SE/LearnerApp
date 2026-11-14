// Exercise: short-lived access tokens for the SandPay dashboard API (fictional), signed and checked
// with jose. Tests: tests/sessions/access-tokens.test.ts
//
// This first draft round-trips a token in a quick manual test - and accepts forged ones. Fix it:
//   1. verifyAccessToken only DECODES the token. Verify the signature with jwtVerify, allowing only
//      HS256, and check the issuer, the audience and the "at+jwt" type header.
//   2. Tokens never expire. Set iat and exp (accessTtlSeconds), and check exp against options.now()
//      with a 30-second clock tolerance (jwtVerify's currentDate and clockTolerance options).
//   3. Give every token a unique "jti", and require sub, exp, iat and jti when verifying.
//   4. Report an expired token as { ok: false, reason: 'expired' } and every other failure as
//      'invalid' - never throw for a bad token.
//   5. Refuse a secret shorter than 32 bytes when the service is created (jose won't).

import { decodeJwt, SignJWT } from 'jose';

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

export function createTokenService(options: TokenServiceOptions): TokenService {
  return {
    async issueAccessToken(userId, roles) {
      return new SignJWT({ roles })
        .setProtectedHeader({ alg: 'HS256' })
        .setIssuer(options.issuer)
        .setAudience(options.audience)
        .setSubject(userId)
        .sign(options.secret);
    },

    async verifyAccessToken(token) {
      try {
        const payload = decodeJwt(token);
        return {
          ok: true,
          userId: String(payload.sub),
          roles: (payload.roles as string[] | undefined) ?? [],
          tokenId: String(payload.jti),
        };
      } catch {
        return { ok: false, reason: 'invalid' };
      }
    },
  };
}
