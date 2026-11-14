// Exercise: read the API's configuration from environment variables - once, at start-up - and fail
// with ONE clear error that lists every problem, instead of crashing later on the first bad value.
// Tests: tests/node/load-config.test.ts

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

/**
 * Builds the configuration from an environment such as `process.env`. Every value in the
 * environment is a string (or missing), so convert and check each one. Treat an empty string
 * like a missing variable. Collect every problem, then throw a single ConfigError; each problem
 * message must start with the variable's name, for example "PORT must be an integer from 1 to 65535".
 */
export function loadConfig(env: Record<string, string | undefined>): AppConfig {
  // TODO: replace this naive version. It trusts every value and checks nothing.
  return {
    port: Number(env.PORT),
    sandpayApiUrl: env.SANDPAY_API_URL as string,
    logLevel: env.LOG_LEVEL as LogLevel,
    nodeEnv: env.NODE_ENV as AppConfig['nodeEnv'],
  };
}
