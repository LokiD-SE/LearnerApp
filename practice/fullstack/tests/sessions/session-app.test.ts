import request from 'supertest';
import { createSessionApp, SESSION_COOKIE, type SessionApp } from '../../exercises/sessions/session-app.js';

const MINUTE = 60_000;
const START = Date.UTC(2026, 10, 14, 9, 0, 0);

/** A fake clock the tests move by hand - no real waiting, no flaky timing. */
function fakeClock() {
  let now = START;
  return { now: () => now, advance: (ms: number) => (now += ms) };
}

/** One known merchant user (fictional): ops@merchant.example / correct-horse. */
async function verifyUser(email: string, password: string): Promise<string | null> {
  return email === 'ops@merchant.example' && password === 'correct-horse' ? 'usr_1001' : null;
}

function setup(clock = fakeClock()): SessionApp & { clock: ReturnType<typeof fakeClock> } {
  const built = createSessionApp({
    verifyUser,
    now: clock.now,
    idleTimeoutMs: 15 * MINUTE,
    absoluteTimeoutMs: 8 * 60 * MINUTE,
  });
  return { ...built, clock };
}

/** The Set-Cookie headers of a response, as an array (supertest gives undefined when there are none). */
function setCookies(res: request.Response): string[] {
  const header: unknown = res.headers['set-cookie'];
  if (header === undefined) return [];
  return Array.isArray(header) ? header.map(String) : [String(header)];
}

/** Splits one Set-Cookie line into its name, value and attributes (attribute names lower-cased). */
function parseSetCookie(line: string) {
  const [pair = '', ...attrs] = line.split(';').map((part) => part.trim());
  const eq = pair.indexOf('=');
  const attributes = new Map<string, string>();
  for (const attr of attrs) {
    const i = attr.indexOf('=');
    if (i === -1) attributes.set(attr.toLowerCase(), '');
    else attributes.set(attr.slice(0, i).toLowerCase(), attr.slice(i + 1));
  }
  return { name: pair.slice(0, eq), value: decodeURIComponent(pair.slice(eq + 1)), attributes };
}

/** The session cookie set by a response - the test fails if there isn't exactly one. */
function sessionCookie(res: request.Response) {
  const cookies = setCookies(res)
    .map(parseSetCookie)
    .filter((c) => c.name === SESSION_COOKIE);
  expect(
    cookies,
    `expected one Set-Cookie for ${SESSION_COOKIE}, got: ${setCookies(res).join(' | ')}`,
  ).toHaveLength(1);
  return cookies[0]!;
}

async function login(built: SessionApp, cookie?: string) {
  const req = request(built.app).post('/login');
  if (cookie) req.set('Cookie', `${SESSION_COOKIE}=${cookie}`);
  return req.send({ email: 'ops@merchant.example', password: 'correct-horse' });
}

function me(built: SessionApp, id: string) {
  return request(built.app).get('/me').set('Cookie', `${SESSION_COOKIE}=${id}`);
}

describe('session-app', { tags: ['@exercise'] }, () => {
  test('login sets the session cookie with Secure, HttpOnly, SameSite=Lax and Path=/ - and no Domain', async () => {
    const built = setup();
    const res = await login(built);
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ userId: 'usr_1001' });
    const cookie = sessionCookie(res);
    expect(cookie.attributes.has('secure')).toBe(true);
    expect(cookie.attributes.has('httponly')).toBe(true);
    expect(cookie.attributes.get('samesite')?.toLowerCase()).toBe('lax');
    expect(cookie.attributes.get('path')).toBe('/');
    expect(cookie.attributes.has('domain'), 'a __Host- cookie must not have a Domain attribute').toBe(false);
  });

  test('the session id is random, has at least 128 bits and is stored on the server', async () => {
    const built = setup();
    const ids = new Set<string>();
    for (let i = 0; i < 20; i++) ids.add(sessionCookie(await login(built)).value);
    expect(ids.size, 'every login must get a different id').toBe(20);
    for (const id of ids) {
      expect(id, 'use base64url or hex of at least 16 random bytes').toMatch(
        /^(?:[A-Za-z0-9_-]{22,}|[0-9a-f]{32,})$/,
      );
      expect(built.sessions.get(id)?.userId).toBe('usr_1001');
    }
  });

  test('a wrong password answers 401 and sets no session cookie', async () => {
    const built = setup();
    const res = await request(built.app)
      .post('/login')
      .send({ email: 'ops@merchant.example', password: 'Tr0ub4dor&3' });
    expect(res.status).toBe(401);
    expect(setCookies(res).filter((c) => c.startsWith(SESSION_COOKIE))).toEqual([]);
    expect(built.sessions.size).toBe(0);
  });

  test('GET /me needs a valid session', async () => {
    const built = setup();
    const id = sessionCookie(await login(built)).value;
    expect((await me(built, id)).body).toEqual({ userId: 'usr_1001' });
    expect((await request(built.app).get('/me')).status).toBe(401);
    expect((await me(built, 'not-a-real-session-id')).status).toBe(401);
  });

  test('session fixation: an id the browser had before login is never kept', async () => {
    const built = setup();
    // An attacker plants a cookie in the victim's browser, then the victim logs in.
    const planted = 'attacker-chosen-id-0000000000000000';
    const res = await login(built, planted);
    const issued = sessionCookie(res).value;
    expect(issued).not.toBe(planted);
    expect((await me(built, planted)).status, 'the planted id must not be logged in').toBe(401);
    expect((await me(built, issued)).status).toBe(200);
  });

  test('logging in again rotates the id and the old one stops working', async () => {
    const built = setup();
    const first = sessionCookie(await login(built)).value;
    const second = sessionCookie(await login(built, first)).value;
    expect(second).not.toBe(first);
    expect((await me(built, first)).status).toBe(401);
    expect(built.sessions.has(first)).toBe(false);
  });

  test('idle timeout: activity keeps the session alive, 15 quiet minutes end it', async () => {
    const built = setup();
    const id = sessionCookie(await login(built)).value;
    built.clock.advance(10 * MINUTE);
    expect((await me(built, id)).status).toBe(200); // used at 10 min - the idle clock restarts
    built.clock.advance(14 * MINUTE);
    expect((await me(built, id)).status).toBe(200); // 24 min after login, but only 14 idle
    built.clock.advance(15 * MINUTE + 1);
    expect((await me(built, id)).status).toBe(401);
    expect(built.sessions.has(id), 'an expired session is removed from the store').toBe(false);
  });

  test('absolute timeout: even a busy session ends 8 hours after login', async () => {
    const built = setup();
    const id = sessionCookie(await login(built)).value;
    for (let elapsed = 0; elapsed < 8 * 60 * MINUTE; elapsed += 10 * MINUTE) {
      expect((await me(built, id)).status).toBe(200);
      built.clock.advance(10 * MINUTE);
    }
    built.clock.advance(1);
    expect((await me(built, id)).status).toBe(401);
  });

  test('logout ends the session on the server and clears the cookie with the same attributes', async () => {
    const built = setup();
    const id = sessionCookie(await login(built)).value;
    const res = await request(built.app).post('/logout').set('Cookie', `${SESSION_COOKIE}=${id}`);
    expect(res.status).toBe(204);
    const cleared = sessionCookie(res);
    expect(cleared.value).toBe('');
    expect(Date.parse(cleared.attributes.get('expires') ?? '')).toBeLessThan(START);
    expect(cleared.attributes.has('secure') && cleared.attributes.get('path') === '/').toBe(true);
    // A copy of the cookie (from a shared computer, a log, a stolen backup) is now useless.
    expect((await me(built, id)).status).toBe(401);
    expect(built.sessions.has(id)).toBe(false);
  });
});
