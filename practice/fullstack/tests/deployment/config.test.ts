import { ConfigError, describeConfig, loadConfig } from '../../exercises/deployment/config.js';

// Test-only values - obviously not real credentials.
const SECRET = 'test-only-session-secret-0123456789abcdef';
const DB_PASSWORD = 'test-only-db-password';
const DATABASE_URL = `postgres://sandpay:${DB_PASSWORD}@db.internal:5432/sandpay`;

/** The smallest valid environment for local development. */
const base = (): Record<string, string | undefined> => ({ DATABASE_URL, SESSION_SECRET: SECRET });

function problemsOf(env: Record<string, string | undefined>): string[] {
  try {
    loadConfig(env);
  } catch (error) {
    expect(error).toBeInstanceOf(ConfigError);
    return (error as ConfigError).problems;
  }
  throw new Error('expected loadConfig to throw a ConfigError');
}

describe('loadConfig', { tags: ['@exercise'] }, () => {
  test('a minimal development environment gets the documented defaults', () => {
    expect(loadConfig(base())).toEqual({
      nodeEnv: 'development',
      port: 3000,
      databaseUrl: DATABASE_URL,
      sessionSecret: SECRET,
      logLevel: 'info',
      shutdownTimeoutMs: 10_000,
      releaseId: 'dev',
      features: { newRefundFlow: false },
    });
  });

  test('reads every variable that is set', () => {
    const config = loadConfig({
      ...base(),
      NODE_ENV: 'production',
      PORT: '8080',
      LOG_LEVEL: 'warn',
      SHUTDOWN_TIMEOUT_MS: '25000',
      RELEASE_ID: '2026-11-14.3',
      FEATURE_NEW_REFUND_FLOW: 'true',
    });
    expect(config).toMatchObject({
      nodeEnv: 'production',
      port: 8080,
      logLevel: 'warn',
      shutdownTimeoutMs: 25_000,
      releaseId: '2026-11-14.3',
      features: { newRefundFlow: true },
    });
  });

  test('"false", "0" and "off" turn a feature flag off - Boolean("false") is true', () => {
    for (const value of ['false', '0', 'off', 'FALSE']) {
      expect(loadConfig({ ...base(), FEATURE_NEW_REFUND_FLOW: value }).features.newRefundFlow).toBe(false);
    }
    expect(problemsOf({ ...base(), FEATURE_NEW_REFUND_FLOW: 'maybe' })).toEqual([
      expect.stringContaining('FEATURE_NEW_REFUND_FLOW'),
    ]);
  });

  test('PORT must be a whole number from 1 to 65535, written in digits', () => {
    for (const port of ['80a', '3e3', '3000.0', ' 3000', '0', '65536', '-1']) {
      expect(problemsOf({ ...base(), PORT: port }), `PORT=${port}`).toEqual([
        expect.stringContaining('PORT'),
      ]);
    }
    expect(loadConfig({ ...base(), PORT: '65535' }).port).toBe(65_535);
  });

  test('an empty value counts as not set', () => {
    expect(loadConfig({ ...base(), PORT: '', LOG_LEVEL: '' })).toMatchObject({
      port: 3000,
      logLevel: 'info',
    });
  });

  test('SHUTDOWN_TIMEOUT_MS must be from 1000 to 60000', () => {
    expect(problemsOf({ ...base(), SHUTDOWN_TIMEOUT_MS: '999' })).toEqual([
      expect.stringContaining('SHUTDOWN_TIMEOUT_MS'),
    ]);
    expect(problemsOf({ ...base(), SHUTDOWN_TIMEOUT_MS: '60001' })).toEqual([
      expect.stringContaining('SHUTDOWN_TIMEOUT_MS'),
    ]);
  });

  test('the database URL and the session secret have no defaults', () => {
    const problems = problemsOf({});
    expect(problems).toHaveLength(2);
    expect(problems).toEqual(
      expect.arrayContaining([
        expect.stringContaining('DATABASE_URL'),
        expect.stringContaining('SESSION_SECRET'),
      ]),
    );
  });

  test('rejects a database URL that is not PostgreSQL and a session secret under 32 characters', () => {
    expect(problemsOf({ ...base(), DATABASE_URL: 'mysql://db.internal/sandpay' })).toEqual([
      expect.stringContaining('DATABASE_URL'),
    ]);
    expect(problemsOf({ ...base(), SESSION_SECRET: 'x'.repeat(31) })).toEqual([
      expect.stringContaining('SESSION_SECRET'),
    ]);
    expect(loadConfig({ ...base(), SESSION_SECRET: 'x'.repeat(32) }).sessionSecret).toHaveLength(32);
  });

  test('NODE_ENV and LOG_LEVEL accept only the documented values', () => {
    expect(problemsOf({ ...base(), NODE_ENV: 'staging' })).toEqual([expect.stringContaining('NODE_ENV')]);
    expect(problemsOf({ ...base(), LOG_LEVEL: 'verbose' })).toEqual([expect.stringContaining('LOG_LEVEL')]);
  });

  test('production needs a RELEASE_ID; other environments default it to "dev"', () => {
    expect(problemsOf({ ...base(), NODE_ENV: 'production' })).toEqual([
      expect.stringContaining('RELEASE_ID'),
    ]);
    expect(loadConfig({ ...base(), NODE_ENV: 'test' }).releaseId).toBe('dev');
  });

  test('reports every problem at once, not only the first', () => {
    const problems = problemsOf({
      NODE_ENV: 'production',
      PORT: '80a',
      DATABASE_URL: 'mysql://db',
      SESSION_SECRET: 'short',
      FEATURE_NEW_REFUND_FLOW: 'maybe',
    });
    for (const name of ['PORT', 'DATABASE_URL', 'SESSION_SECRET', 'FEATURE_NEW_REFUND_FLOW', 'RELEASE_ID']) {
      expect(
        problems.some((problem) => problem.includes(name)),
        name,
      ).toBe(true);
    }
  });

  test('never puts a value it was given into the error', () => {
    const shortSecret = 'too-short-but-still-secret';
    try {
      loadConfig({
        SESSION_SECRET: shortSecret,
        DATABASE_URL: `mysql://sandpay:${DB_PASSWORD}@db.internal/sandpay`,
      });
      throw new Error('expected a ConfigError');
    } catch (error) {
      const text = `${(error as Error).message}\n${(error as ConfigError).problems?.join('\n')}`;
      expect(text).not.toContain(shortSecret);
      expect(text).not.toContain(DB_PASSWORD);
    }
  });

  test('the configuration cannot be changed after start-up', () => {
    const config = loadConfig(base());
    expect(Object.isFrozen(config)).toBe(true);
    expect(Object.isFrozen(config.features)).toBe(true);
  });
});

describe('describeConfig', { tags: ['@exercise'] }, () => {
  test('hides the secret and the database password, keeps everything else', () => {
    const described = describeConfig(loadConfig({ ...base(), FEATURE_NEW_REFUND_FLOW: 'on' }));
    const text = JSON.stringify(described);
    expect(text).not.toContain(SECRET);
    expect(text).not.toContain(DB_PASSWORD);
    expect(described).toMatchObject({
      nodeEnv: 'development',
      port: 3000,
      sessionSecret: '[redacted]',
      releaseId: 'dev',
      'features.newRefundFlow': true,
    });
    expect(described.databaseUrl).toBe('postgres://sandpay:REDACTED@db.internal:5432/sandpay');
  });
});
