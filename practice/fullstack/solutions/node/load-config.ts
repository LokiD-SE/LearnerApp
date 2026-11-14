// Reference solution for exercises/node/load-config.ts.

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface AppConfig {
  /** PORT - an integer from 1 to 65535. Default 3000. */
  port: number;
  /** SANDPAY_API_URL - required; an absolute https URL. Stored without a trailing slash. */
  sandpayApiUrl: string;
  /** LOG_LEVEL - debug, info, warn or error. Default info. */
  logLevel: LogLevel;
  /** NODE_ENV - production, development or test. Default development. */
  nodeEnv: 'production' | 'development' | 'test';
}

/** Thrown when the environment is invalid. `problems` has one message per bad variable. */
export class ConfigError extends Error {
  constructor(readonly problems: string[]) {
    super(`Invalid configuration:\n- ${problems.join('\n- ')}`);
    this.name = 'ConfigError';
  }
}

const LOG_LEVELS: readonly LogLevel[] = ['debug', 'info', 'warn', 'error'];
const NODE_ENVS: readonly AppConfig['nodeEnv'][] = ['production', 'development', 'test'];

function oneOf<T extends string>(allowed: readonly T[], value: string): value is T {
  return (allowed as readonly string[]).includes(value);
}

export function loadConfig(env: Record<string, string | undefined>): AppConfig {
  const problems: string[] = [];
  // An empty string counts as missing: `PORT=` in a .env file sets PORT to ''.
  const read = (name: string): string | undefined => {
    const value = env[name]?.trim();
    return value ? value : undefined;
  };

  let port = 3000;
  const rawPort = read('PORT');
  if (rawPort !== undefined) {
    // Number('') is 0 and Number('3000abc') is NaN; a regular expression rejects '3e3' and '30.5' too.
    const parsed = Number(rawPort);
    if (/^\d+$/.test(rawPort) && parsed >= 1 && parsed <= 65535) port = parsed;
    else problems.push(`PORT must be an integer from 1 to 65535, got "${rawPort}"`);
  }

  let sandpayApiUrl = '';
  const rawUrl = read('SANDPAY_API_URL');
  if (rawUrl === undefined) problems.push('SANDPAY_API_URL is required');
  else if (!URL.canParse(rawUrl) || new URL(rawUrl).protocol !== 'https:')
    problems.push(`SANDPAY_API_URL must be an absolute https URL, got "${rawUrl}"`);
  else sandpayApiUrl = rawUrl.replace(/\/+$/, '');

  let logLevel: LogLevel = 'info';
  const rawLevel = read('LOG_LEVEL');
  if (rawLevel !== undefined) {
    if (oneOf(LOG_LEVELS, rawLevel)) logLevel = rawLevel;
    else problems.push(`LOG_LEVEL must be one of ${LOG_LEVELS.join(', ')}, got "${rawLevel}"`);
  }

  let nodeEnv: AppConfig['nodeEnv'] = 'development';
  const rawEnv = read('NODE_ENV');
  if (rawEnv !== undefined) {
    if (oneOf(NODE_ENVS, rawEnv)) nodeEnv = rawEnv;
    else problems.push(`NODE_ENV must be one of ${NODE_ENVS.join(', ')}, got "${rawEnv}"`);
  }

  if (problems.length > 0) throw new ConfigError(problems);
  return { port, sandpayApiUrl, logLevel, nodeEnv };
}
