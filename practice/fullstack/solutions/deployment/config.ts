// Exercise: load and validate the SandPay dashboard API's (fictional) configuration from the
// environment, once, at start-up. Tests: tests/deployment/config.test.ts
import * as z from 'zod';

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

/** Whole numbers written in digits only: "3000" yes; "", " 3000", "3e3", "3000.0", "80a" no. */
const digits = (name: string, min: number, max: number) =>
  z
    .string()
    .regex(/^\d+$/, `${name} must be a whole number`)
    .transform(Number)
    .pipe(
      z.number().int().min(min, `${name} must be at least ${min}`).max(max, `${name} must be at most ${max}`),
    );

const Env = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: digits('PORT', 1, 65_535).default(3000),
  DATABASE_URL: z
    .string({ error: 'DATABASE_URL is required' })
    .refine((value) => /^postgres(ql)?:\/\/.+/.test(value) && URL.canParse(value), {
      message: 'DATABASE_URL must be a postgres:// or postgresql:// URL',
    }),
  SESSION_SECRET: z
    .string({ error: 'SESSION_SECRET is required' })
    .min(32, 'SESSION_SECRET must be at least 32 characters'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  SHUTDOWN_TIMEOUT_MS: digits('SHUTDOWN_TIMEOUT_MS', 1_000, 60_000).default(10_000),
  RELEASE_ID: z.string().min(1).optional(),
  FEATURE_NEW_REFUND_FLOW: z
    .stringbool({ error: 'FEATURE_NEW_REFUND_FLOW must be true or false' })
    .default(false),
});

/**
 * Reads the configuration from `env` (process.env in the app, a plain object in tests).
 * Every problem is reported at once; the returned object is frozen.
 */
export function loadConfig(env: Record<string, string | undefined>): AppConfig {
  // An empty string counts as "not set", so `PORT=` falls back to the default instead of failing oddly.
  const present = Object.fromEntries(
    Object.entries(env).filter(([, value]) => value !== undefined && value !== ''),
  );
  const result = Env.safeParse(present);
  // Messages only: zod issues can carry the received input, and a secret must never reach a log.
  const problems = result.success
    ? []
    : result.error.issues.map((issue) => {
        const name = String(issue.path[0] ?? 'environment');
        return issue.message.startsWith(name) ? issue.message : `${name}: ${issue.message}`;
      });
  // Checked here, not in a zod refinement: refinements are skipped while other fields fail, and
  // every problem should be reported in one go.
  if (present.NODE_ENV === 'production' && present.RELEASE_ID === undefined) {
    problems.push('RELEASE_ID is required in production');
  }
  if (!result.success || problems.length > 0) throw new ConfigError(problems);
  const e = result.data;
  return Object.freeze({
    nodeEnv: e.NODE_ENV,
    port: e.PORT,
    databaseUrl: e.DATABASE_URL,
    sessionSecret: e.SESSION_SECRET,
    logLevel: e.LOG_LEVEL,
    shutdownTimeoutMs: e.SHUTDOWN_TIMEOUT_MS,
    releaseId: e.RELEASE_ID ?? 'dev',
    features: Object.freeze({ newRefundFlow: e.FEATURE_NEW_REFUND_FLOW }),
  });
}

/** A copy that is safe to log at start-up: the session secret and the database password are hidden. */
export function describeConfig(config: AppConfig): Record<string, string | number | boolean> {
  const url = new URL(config.databaseUrl);
  if (url.password) url.password = 'REDACTED';
  return {
    nodeEnv: config.nodeEnv,
    port: config.port,
    databaseUrl: url.toString(),
    sessionSecret: '[redacted]',
    logLevel: config.logLevel,
    shutdownTimeoutMs: config.shutdownTimeoutMs,
    releaseId: config.releaseId,
    'features.newRefundFlow': config.features.newRefundFlow,
  };
}
