// Exercise: the telemetry middleware of the SandPay dashboard API (fictional) - one structured JSON
// log line per request, correlated with the trace, and a request-duration histogram exposed in the
// Prometheus text format. Names follow the OpenTelemetry HTTP semantic conventions.
// Tests: tests/observability/http-telemetry.test.ts

import type { RequestHandler } from 'express';
import { continueTrace, type TraceContext } from './trace-context.js';

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

interface Series {
  labels: Labels;
  /** counts[i] = observations with value <= buckets[i] and > buckets[i-1] (not yet cumulative). */
  counts: number[];
  sum: number;
  count: number;
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
  private readonly series = new Map<string, Series>();

  constructor(
    readonly name: string,
    readonly help: string,
    readonly buckets: readonly number[] = HTTP_DURATION_BUCKETS,
  ) {}

  observe(labels: Labels, value: number): void {
    const key = labelText(labels);
    let series = this.series.get(key);
    if (!series) {
      series = { labels: { ...labels }, counts: this.buckets.map(() => 0), sum: 0, count: 0 };
      this.series.set(key, series);
    }
    const index = this.buckets.findIndex((bound) => value <= bound);
    if (index >= 0) series.counts[index] = (series.counts[index] ?? 0) + 1;
    series.sum += value;
    series.count += 1;
  }

  /** How many distinct label sets (time series) this histogram holds. */
  seriesCount(): number {
    return this.series.size;
  }

  render(): string {
    const lines = [`# HELP ${this.name} ${this.help}`, `# TYPE ${this.name} histogram`];
    for (const key of [...this.series.keys()].sort()) {
      const series = this.series.get(key);
      if (!series) continue;
      let cumulative = 0;
      this.buckets.forEach((bound, i) => {
        cumulative += series.counts[i] ?? 0;
        lines.push(`${this.name}_bucket${labelText(series.labels, ['le', String(bound)])} ${cumulative}`);
      });
      lines.push(`${this.name}_bucket${labelText(series.labels, ['le', '+Inf'])} ${series.count}`);
      lines.push(`${this.name}_sum${key} ${series.sum}`);
      lines.push(`${this.name}_count${key} ${series.count}`);
    }
    return lines.join('\n') + '\n';
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
  const now = options.now ?? (() => performance.now());
  const wallClock = options.wallClock ?? (() => new Date());
  return (req, res, next) => {
    const start = now();
    const trace: TraceContext = continueTrace(req.get('traceparent'), {
      newSpanId: options.newSpanId,
      newTraceId: options.newTraceId,
    });
    res.locals.trace = trace;

    res.on('finish', () => {
      const durationMs = now() - start;
      const status = res.statusCode;
      const method = KNOWN_METHODS.has(req.method) ? req.method : '_OTHER';
      const routePath: unknown = req.route?.path;
      const route = typeof routePath === 'string' ? req.baseUrl + routePath : undefined;

      const labels: Labels = { http_request_method: method, http_response_status_code: String(status) };
      if (route !== undefined) labels.http_route = route;
      options.histogram.observe(labels, durationMs / 1000);

      const record: Record<string, unknown> = {
        time: wallClock().toISOString(),
        level: status >= 500 ? 'error' : 'info',
        msg: 'request completed',
        trace_id: trace.traceId,
        span_id: trace.parentId,
        'http.request.method': method,
        'http.route': route,
        'url.path': req.originalUrl.split('?')[0],
        'http.response.status_code': status,
        'error.type': status >= 500 ? String(status) : undefined,
        duration_ms: Math.round(durationMs * 1000) / 1000,
      };
      for (const key of Object.keys(record)) if (record[key] === undefined) delete record[key];
      options.log(record);
    });
    next();
  };
}
