// Exercise: server-side sessions for the SandPay merchant dashboard (fictional) - a login that
// rotates the session id, a cookie with safe attributes, idle and absolute timeouts, and a logout
// that really ends the session. Tests: tests/sessions/session-app.test.ts
//
// This first draft "works" in a quick manual test, but it has the classic session bugs. Fix them:
//   1. The cookie is called `sid` and only HttpOnly - use SESSION_COOKIE with Secure, HttpOnly,
//      SameSite=Lax and Path=/ (and the same attributes when you clear it).
//   2. The id is a counter - generate at least 128 bits from a CSPRNG (node:crypto randomBytes).
//   3. Login keeps an id the browser already had (session fixation) - always issue a new one and
//      delete the old one.
//   4. There are no timeouts - enforce idleTimeoutMs and absoluteTimeoutMs using options.now().
//   5. Logout only clears the cookie - delete the session on the server too.

import cookieParser from 'cookie-parser';
import express, { type Express } from 'express';

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

let counter = 1000;

export function createSessionApp(options: SessionAppOptions): SessionApp {
  const sessions = new Map<string, Session>();
  const app = express();
  app.use(express.json());
  app.use(cookieParser());

  app.post('/login', async (req, res) => {
    const { email, password } = (req.body ?? {}) as { email?: string; password?: string };
    const userId = await options.verifyUser(String(email), String(password));
    if (userId === null) {
      res.status(401).json({ error: 'invalid_credentials' });
      return;
    }
    const cookies = req.cookies as Record<string, string | undefined>;
    const id = cookies.sid ?? String(counter++);
    const now = options.now();
    sessions.set(id, { userId, createdAt: now, lastSeenAt: now });
    res.cookie('sid', id, { httpOnly: true });
    res.status(200).json({ userId });
  });

  app.get('/me', (req, res) => {
    const cookies = req.cookies as Record<string, string | undefined>;
    const session = cookies.sid === undefined ? undefined : sessions.get(cookies.sid);
    if (session === undefined) {
      res.status(401).json({ error: 'not_authenticated' });
      return;
    }
    res.json({ userId: session.userId });
  });

  app.post('/logout', (req, res) => {
    res.clearCookie('sid');
    res.status(204).end();
  });

  return { app, sessions };
}
