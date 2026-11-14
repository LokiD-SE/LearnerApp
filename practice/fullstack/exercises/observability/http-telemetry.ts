// Exercise: the telemetry middleware of the SandPay dashboard API (fictional) - one structured JSON
// log line per request, correlated with the trace, and a request-duration histogram exposed in the
// Prometheus text format. Names follow the OpenTelemetry HTTP semantic conventions.
// Tests: tests/observability/http-telemetry.test.ts

import type { RequestHandler } from 'express';
import { continueTrace } from './trace-context.js';

/** The bucket boundaries (seconds) the OpenTelemetry semantic conventions advise for http.server.request.duration. */
export const HTTP_DURATION_BUCKETS = [
  0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10,
];

export type Labels = Record<string, string>;

/** Escapes a label value for the Prometheus text format: backslash, double quote and line feed. */
function escapeLabelValue(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n');
}

/** `{a="1",b="2"}` with keys sorted, or '' for no labels. `extra` (such as le) goes last. */
function labelText(labels: Labels, extra?: [string, string]): string {
  const pairs = Object.keys(labels)
    .sort()
    .map((key) => `${key}="${escapeLabelValue(labels[key] ?? '')}"`);
  if (extra) pairs.push(`${extra[0]}="${escapeLabelValue(extra[1])}"`);
  return pairs.length === 0 ? '' : `{${pairs.join(',')}}`;
}

/**
 * A classic Prometheus histogram: one series per distinct label set, each with a counter per bucket.
 *
 * `render()` returns the text exposition format:
 *
 *     # HELP <name> <help>
 *     # TYPE <name> histogram
 *     <name>_bucket{<labels>,le="0.005"} <cumulative count>
 *     ... one line per bucket, then le="+Inf" (equal to the count)
 *     <name>_sum{<labels>} <sum of observed values>
 *     <name>_count{<labels>} <number of observations>
 *
 * Buckets are CUMULATIVE (le means "less than or equal"). Series are sorted by their label text so
 * the output is reproducible; label keys are sorted inside each series; `le` comes last.
 */
export class Histogram {
  constructor(
    readonly name: string,
    readonly help: string,
    readonly buckets: readonly number[] = HTTP_DURATION_BUCKETS,
  ) {}

  observe(labels: Labels, value: number): void {
    // TODO: find or create the series for these labels; count the value in its bucket, add to sum and count.
    void labels;
    void value;
  }

  /** How many distinct label sets (time series) this histogram holds. */
  seriesCount(): number {
    // TODO
    return 0;
  }

  render(): string {
    // TODO: HELP and TYPE lines, then for each series (sorted): cumulative buckets, +Inf, _sum, _count.
    void labelText;
    return '';
  }
}

/** Methods the OpenTelemetry conventions treat as known (RFC 9110, PATCH and QUERY); others become _OTHER. */
const KNOWN_METHODS = new Set([
  'CONNECT',
  'DELETE',
  'GET',
  'HEAD',
  'OPTIONS',
  'PATCH',
  'POST',
  'PUT',
  'TRACE',
  'QUERY',
]);

export interface TelemetryOptions {
  /** Receives each log record (one per request). In production: write JSON.stringify(record) + '\n' to stdout. */
  log: (record: Record<string, unknown>) => void;
  /** The duration histogram, named http_server_request_duration_seconds. */
  histogram: Histogram;
  /** A monotonic clock in milliseconds. Defaults to performance.now(). */
  now?: () => number;
  /** The wall clock for the log's `time` field. Defaults to () => new Date(). */
  wallClock?: () => Date;
  /** Passed to continueTrace (tests use it to make ids predictable). */
  newSpanId?: () => string;
  newTraceId?: () => string;
}

/**
 * Telemetry for every request. Mount it FIRST, before the routes.
 *
 * On the way in:
 * - continue the trace from the incoming `traceparent` header (continueTrace) and store the context in
 *   `res.locals.trace` so handlers can log with it and pass `formatTraceparent(...)` to downstream calls;
 * - remember the start time from `now()`.
 *
 * When the response has finished (`res.on('finish')`):
 * - the route: the matched route TEMPLATE `req.baseUrl + req.route.path` (for example
 *   `/merchants/:merchantId/orders`) - never the raw URL; undefined when no route matched (a 404);
 * - the method: `req.method` when known, otherwise `_OTHER`;
 * - observe the duration in SECONDS with labels `http_request_method`, `http_response_status_code` and
 *   (only when a route matched) `http_route`;
 * - log ONE record with exactly these fields (leave out the ones that are undefined):
 *     time (ISO 8601), level ('error' for 5xx, otherwise 'info'), msg ('request completed'),
 *     trace_id, span_id, 'http.request.method', 'http.route', 'url.path' (the path WITHOUT the query
 *     string - queries can carry tokens), 'http.response.status_code' (a number),
 *     'error.type' (the status code as a string, only for 5xx), duration_ms (a number of milliseconds, rounded to 3 decimals).
 */
export function telemetry(options: TelemetryOptions): RequestHandler {
  // TODO: continue the trace, store it in res.locals.trace, note the start time, and on 'finish'
  // observe the histogram and log one record.
  void options;
  void continueTrace;
  void KNOWN_METHODS;
  return (req, res, next) => {
    next();
  };
}
