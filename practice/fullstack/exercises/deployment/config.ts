// Exercise: load and validate the SandPay dashboard API's (fictional) configuration from the
// environment, once, at start-up. Tests: tests/deployment/config.test.ts
//
// This first draft "works on my machine" - and would start in production with a guessable session
// secret and a feature flag stuck on. Rewrite loadConfig (zod 4 is installed) so that:
//   1. NODE_ENV is development | test | production (default development); LOG_LEVEL is
//      debug | info | warn | error (default info).
//   2. PORT is a whole number written in digits only, 1-65535 (default 3000). "80a", "3e3", " 3000"
//      and "3000.0" are errors - Number() and parseInt() accept some of them.
//      SHUTDOWN_TIMEOUT_MS follows the same rule, 1000-60000 (default 10000).
//   3. DATABASE_URL (a postgres:// or postgresql:// URL) and SESSION_SECRET (32+ characters) are
//      REQUIRED in every environment - no defaults in the code.
//   4. FEATURE_NEW_REFUND_FLOW is a boolean string: "true"/"1"/"on"/"yes" and "false"/"0"/"off"/"no"
//      (any case), default false; anything else is an error. (z.stringbool does exactly this.)
//   5. RELEASE_ID is required when NODE_ENV is production; elsewhere it defaults to "dev".
//   6. An empty value (PORT=) counts as not set.
//   7. Every problem is reported at once in a ConfigError, one "NAME ..." entry per problem, and no
//      problem or message ever contains a value it was given (secrets end up in logs that way).
//   8. The returned config and its features object are frozen.
// Then make describeConfig safe to log: sessionSecret "[redacted]", the database password replaced
// by "REDACTED" (new URL() can do it), everything else unchanged.

/** Thrown by loadConfig. `problems` lists every bad variable as "NAME: what is wrong" - never its value. */
export class ConfigError extends Error {
  constructor(readonly problems: string[]) {
    super(`Invalid configuration:\n${problems.map((problem) => `  - ${problem}`).join('\n')}`);
    this.name = 'ConfigError';
  }
}

export interface AppConfig {
  readonly nodeEnv: 'development' | 'test' | 'production';
  readonly port: number;
  readonly databaseUrl: string;
  readonly sessionSecret: string;
  readonly logLevel: 'debug' | 'info' | 'warn' | 'error';
  readonly shutdownTimeoutMs: number;
  readonly releaseId: string;
  readonly features: { readonly newRefundFlow: boolean };
}

export function loadConfig(env: Record<string, string | undefined>): AppConfig {
  const port = parseInt(env.PORT ?? '3000', 10);
  if (Number.isNaN(port)) throw new ConfigError([`PORT: ${env.PORT} is not a number`]);
  return {
    nodeEnv: (env.NODE_ENV ?? 'development') as AppConfig['nodeEnv'],
    port,
    databaseUrl: env.DATABASE_URL ?? 'postgres://postgres:postgres@localhost:5432/sandpay',
    sessionSecret: env.SESSION_SECRET ?? 'dev-secret',
    logLevel: (env.LOG_LEVEL ?? 'info') as AppConfig['logLevel'],
    shutdownTimeoutMs: Number(env.SHUTDOWN_TIMEOUT_MS ?? 10_000),
    releaseId: env.RELEASE_ID ?? 'dev',
    features: { newRefundFlow: Boolean(env.FEATURE_NEW_REFUND_FLOW) },
  };
}

/** A copy that is safe to log at start-up: the session secret and the database password are hidden. */
export function describeConfig(config: AppConfig): Record<string, string | number | boolean> {
  return {
    nodeEnv: config.nodeEnv,
    port: config.port,
    databaseUrl: config.databaseUrl,
    sessionSecret: config.sessionSecret,
    logLevel: config.logLevel,
    shutdownTimeoutMs: config.shutdownTimeoutMs,
    releaseId: config.releaseId,
    'features.newRefundFlow': config.features.newRefundFlow,
  };
}
