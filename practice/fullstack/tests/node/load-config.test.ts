import { ConfigError, loadConfig } from '../../exercises/node/load-config.js';

const valid = { SANDPAY_API_URL: 'https://api.sandpay.example' };

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
  test('uses the defaults when only the required variable is set', () => {
    expect(loadConfig(valid)).toEqual({
      port: 3000,
      sandpayApiUrl: 'https://api.sandpay.example',
      logLevel: 'info',
      nodeEnv: 'development',
    });
  });

  test('converts and keeps valid values', () => {
    expect(
      loadConfig({
        PORT: '8080',
        SANDPAY_API_URL: 'https://sandbox.sandpay.example/v1/',
        LOG_LEVEL: 'debug',
        NODE_ENV: 'production',
      }),
    ).toEqual({
      port: 8080,
      sandpayApiUrl: 'https://sandbox.sandpay.example/v1',
      logLevel: 'debug',
      nodeEnv: 'production',
    });
  });

  test('treats empty strings as missing', () => {
    expect(loadConfig({ ...valid, PORT: '', LOG_LEVEL: '' })).toMatchObject({ port: 3000, logLevel: 'info' });
    expect(problemsOf({ SANDPAY_API_URL: '' })).toEqual([expect.stringMatching(/^SANDPAY_API_URL/)]);
  });

  test.each(['0', '65536', '30.5', '3e3', 'eighty', '-1', '3000abc'])('rejects PORT=%s', (port) => {
    expect(problemsOf({ ...valid, PORT: port })).toEqual([expect.stringMatching(/^PORT/)]);
  });

  test('requires SANDPAY_API_URL to be an absolute https URL', () => {
    expect(problemsOf({})).toEqual([expect.stringMatching(/^SANDPAY_API_URL/)]);
    expect(problemsOf({ SANDPAY_API_URL: 'http://api.sandpay.example' })).toHaveLength(1);
    expect(problemsOf({ SANDPAY_API_URL: 'api.sandpay.example' })).toHaveLength(1);
  });

  test('rejects unknown log levels and environments', () => {
    expect(problemsOf({ ...valid, LOG_LEVEL: 'verbose' })).toEqual([expect.stringMatching(/^LOG_LEVEL/)]);
    expect(problemsOf({ ...valid, NODE_ENV: 'prod' })).toEqual([expect.stringMatching(/^NODE_ENV/)]);
  });

  test('reports every problem at once, in one error', () => {
    const problems = problemsOf({ PORT: 'eighty', LOG_LEVEL: 'loud', NODE_ENV: 'staging' });
    expect(problems).toHaveLength(4);
    for (const name of ['PORT', 'SANDPAY_API_URL', 'LOG_LEVEL', 'NODE_ENV'])
      expect(problems.some((p) => p.startsWith(name))).toBe(true);
  });

  test('does not read process.env - only the object it is given', () => {
    process.env.SANDPAY_API_URL = 'https://from-process.sandpay.example';
    try {
      expect(problemsOf({})).toEqual([expect.stringMatching(/^SANDPAY_API_URL/)]);
    } finally {
      delete process.env.SANDPAY_API_URL;
    }
  });
});
