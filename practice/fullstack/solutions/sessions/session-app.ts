// Exercise: server-side sessions for the SandPay merchant dashboard (fictional) - a login that
// rotates the session id, a cookie with safe attributes, idle and absolute timeouts, and a logout
// that really ends the session. Tests: tests/sessions/session-app.test.ts

import { randomBytes } from 'node:crypto';
import cookieParser from 'cookie-parser';
import express, { type Express, type Response } from 'express';

/** The session cookie's name. The __Host- prefix makes browsers insist on Secure, Path=/ and no Domain. */
export const SESSION_COOKIE = '__Host-sid';

export interface Session {
  userId: string;
  /** When the session was created (ms since the epoch) - the start of the absolute timeout. */
  createdAt: number;
  /** When the session was last used (ms since the epoch) - the start of the idle timeout. */
  lastSeenAt: number;
}

export interface SessionAppOptions {
  /** Checks a login. Returns the user's id, or null for a wrong email or password. */
  verifyUser(email: string, password: string): Promise<string | null>;
  /** The current time in ms since the epoch. Tests pass a fake clock. */
  now(): number;
  /** End a session that has not been used for this long (ms). */
  idleTimeoutMs: number;
  /** End a session this long after it was created (ms), however active it is. */
  absoluteTimeoutMs: number;
}

export interface SessionApp {
  app: Express;
  /** The server-side session store: session id -> session. Exposed so tests can inspect it. */
  sessions: Map<string, Session>;
}

/** The attributes every Set-Cookie for the session uses - including the one that clears it. */
const cookieOptions = { httpOnly: true, secure: true, sameSite: 'lax', path: '/' } as const;

/** 32 random bytes from the operating system's CSPRNG = 256 bits, 43 base64url characters. */
function newSessionId(): string {
  return randomBytes(32).toString('base64url');
}

export function createSessionApp(options: SessionAppOptions): SessionApp {
  const sessions = new Map<string, Session>();
  const app = express();
  app.use(express.json());
  app.use(cookieParser());

  function clearSessionCookie(res: Response): void {
    res.clearCookie(SESSION_COOKIE, cookieOptions);
  }

  /** The id from the request's cookie, if the request sent one. */
  function cookieId(cookies: unknown): string | undefined {
    if (typeof cookies !== 'object' || cookies === null) return undefined;
    const value: unknown = (cookies as Record<string, unknown>)[SESSION_COOKIE];
    return typeof value === 'string' && value !== '' ? value : undefined;
  }

  app.post('/login', async (req, res) => {
    const body: unknown = req.body;
    const { email, password } = (typeof body === 'object' && body !== null ? body : {}) as Record<
      string,
      unknown
    >;
    if (typeof email !== 'string' || typeof password !== 'string') {
      res.status(400).json({ error: 'invalid_request' });
      return;
    }
    const userId = await options.verifyUser(email, password);
    if (userId === null) {
      res.status(401).json({ error: 'invalid_credentials' });
      return;
    }
    // Session fixation defence: never keep an id that existed before the login - whoever planted or
    // saw it must not inherit the authenticated session. Delete it and issue a brand-new id.
    const previous = cookieId(req.cookies);
    if (previous !== undefined) sessions.delete(previous);
    const id = newSessionId();
    const now = options.now();
    sessions.set(id, { userId, createdAt: now, lastSeenAt: now });
    res.cookie(SESSION_COOKIE, id, cookieOptions);
    res.status(200).json({ userId });
  });

  app.get('/me', (req, res) => {
    const id = cookieId(req.cookies);
    const session = id === undefined ? undefined : sessions.get(id);
    if (id === undefined || session === undefined) {
      res.status(401).json({ error: 'not_authenticated' });
      return;
    }
    const now = options.now();
    const idle = now - session.lastSeenAt > options.idleTimeoutMs;
    const tooOld = now - session.createdAt > options.absoluteTimeoutMs;
    if (idle || tooOld) {
      sessions.delete(id);
      clearSessionCookie(res);
      res.status(401).json({ error: 'session_expired' });
      return;
    }
    session.lastSeenAt = now;
    res.json({ userId: session.userId });
  });

  app.post('/logout', (req, res) => {
    const id = cookieId(req.cookies);
    if (id !== undefined) sessions.delete(id); // the server forgets it: a copied cookie is now useless
    clearSessionCookie(res);
    res.status(204).end();
  });

  return { app, sessions };
}
