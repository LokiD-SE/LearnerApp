// Exercise: read and continue a W3C Trace Context `traceparent` header, the way a server joins a
// distributed trace (W3C Recommendation "Trace Context", 23 November 2021, sections 3.2 and 3.4).
// Tests: tests/observability/trace-context.test.ts

import { randomBytes } from 'node:crypto';

/** The parts of a traceparent this service uses. Ids are lowercase hex. */
export interface TraceContext {
  /** 32 lowercase hex characters (16 bytes); never all zeros. */
  traceId: string;
  /** 16 lowercase hex characters (8 bytes); never all zeros. In a span this is the span id. */
  parentId: string;
  /** The `sampled` bit (the lowest bit of trace-flags). */
  sampled: boolean;
}

/** Generates `bytes` random bytes as lowercase hex, never all zeros (the spec forbids all-zero ids). */
export function randomHexId(bytes: number): string {
  for (;;) {
    const id = randomBytes(bytes).toString('hex');
    if (!/^0+$/.test(id)) return id;
  }
}

const HEX = (n: number) => new RegExp(`^[0-9a-f]{${n}}$`);
const VERSION = HEX(2);
const TRACE_ID = HEX(32);
const PARENT_ID = HEX(16);
const FLAGS = HEX(2);

/**
 * Parses a `traceparent` header value. Returns null when the header must be ignored (the caller then
 * starts a new trace).
 *
 * - `version`: 2 lowercase hex characters followed by "-"; `ff` is invalid.
 * - Version `00`: exactly `version-traceid-parentid-flags`, 55 characters, nothing more.
 * - A higher version (01-fe): at least 55 characters; parse the same three fields at the same
 *   positions; after the flags there must be either the end of the string or a "-" (future fields,
 *   which you must not interpret).
 * - trace-id: 32 lowercase hex, not all zeros. parent-id: 16 lowercase hex, not all zeros.
 * - trace-flags: 2 lowercase hex; `sampled` is bit 0 - mask it, don't compare the whole byte to 01.
 */
export function parseTraceparent(header: string | undefined): TraceContext | null {
  if (header === undefined) return null;
  const version = header.slice(0, 2);
  if (!VERSION.test(version) || header[2] !== '-' || version === 'ff') return null;
  if (header.length < 55) return null;
  if (version === '00' && header.length !== 55) return null;
  if (header.length > 55 && header[55] !== '-') return null;

  const traceId = header.slice(3, 35);
  const parentId = header.slice(36, 52);
  const flags = header.slice(53, 55);
  if (header[35] !== '-' || header[52] !== '-') return null;
  if (!TRACE_ID.test(traceId) || /^0+$/.test(traceId)) return null;
  if (!PARENT_ID.test(parentId) || /^0+$/.test(parentId)) return null;
  if (!FLAGS.test(flags)) return null;

  return { traceId, parentId, sampled: (parseInt(flags, 16) & 0x01) === 0x01 };
}

/**
 * Formats a context as a version `00` traceparent - the highest version this code knows, which is
 * also how a higher incoming version is "downgraded". Only the sampled flag may be set: the spec
 * says vendors MUST set the other (reserved) flags to zero.
 */
export function formatTraceparent(context: TraceContext): string {
  return `00-${context.traceId}-${context.parentId}-${context.sampled ? '01' : '00'}`;
}

export interface ContinueOptions {
  /** Makes a new 8-byte span id. Defaults to randomHexId(8). */
  newSpanId?: () => string;
  /** Makes a new 16-byte trace id. Defaults to randomHexId(16). */
  newTraceId?: () => string;
  /** The recording decision when this service starts a new trace. Defaults to true. */
  sampleNewTrace?: boolean;
}

/**
 * The context of the span this service creates for an incoming request.
 *
 * - A valid incoming traceparent: join its trace - same traceId, same sampled decision, and a NEW
 *   parentId (this service's span id; the incoming parent-id is the caller's span).
 * - Missing or invalid: restart - a new traceId and span id, sampled = sampleNewTrace.
 */
export function continueTrace(header: string | undefined, options: ContinueOptions = {}): TraceContext {
  const newSpanId = options.newSpanId ?? (() => randomHexId(8));
  const newTraceId = options.newTraceId ?? (() => randomHexId(16));
  const incoming = parseTraceparent(header);
  if (incoming) return { traceId: incoming.traceId, parentId: newSpanId(), sampled: incoming.sampled };
  return { traceId: newTraceId(), parentId: newSpanId(), sampled: options.sampleNewTrace ?? true };
}
