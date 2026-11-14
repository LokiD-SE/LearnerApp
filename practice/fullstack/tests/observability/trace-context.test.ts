import {
  continueTrace,
  formatTraceparent,
  parseTraceparent,
} from '../../exercises/observability/trace-context.js';

// The examples come from the W3C Trace Context Recommendation (section 3.2.3).
const TRACE_ID = '4bf92f3577b34da6a3ce929d0e0e4736';
const PARENT_ID = '00f067aa0ba902b7';
const SAMPLED = `00-${TRACE_ID}-${PARENT_ID}-01`;
const NOT_SAMPLED = `00-${TRACE_ID}-${PARENT_ID}-00`;

describe('parseTraceparent', { tags: ['@exercise'] }, () => {
  test('reads the spec examples, sampled and not sampled', () => {
    expect(parseTraceparent(SAMPLED)).toEqual({ traceId: TRACE_ID, parentId: PARENT_ID, sampled: true });
    expect(parseTraceparent(NOT_SAMPLED)).toEqual({ traceId: TRACE_ID, parentId: PARENT_ID, sampled: false });
  });

  test('masks the sampled bit instead of comparing the whole flags byte', () => {
    expect(parseTraceparent(`00-${TRACE_ID}-${PARENT_ID}-09`)?.sampled).toBe(true);
    expect(parseTraceparent(`00-${TRACE_ID}-${PARENT_ID}-08`)?.sampled).toBe(false);
  });

  test.each([
    ['a missing header', undefined],
    ['an empty header', ''],
    ['uppercase hex', `00-${TRACE_ID.toUpperCase()}-${PARENT_ID}-01`],
    ['an all-zero trace-id', `00-${'0'.repeat(32)}-${PARENT_ID}-01`],
    ['an all-zero parent-id', `00-${TRACE_ID}-${'0'.repeat(16)}-01`],
    ['the forbidden version ff', `ff-${TRACE_ID}-${PARENT_ID}-01`],
    ['a version that is not hex', `0g-${TRACE_ID}-${PARENT_ID}-01`],
    ['version 00 with an extra field', `${SAMPLED}-extra`],
    ['a trace-id one character short', `00-${TRACE_ID.slice(1)}-${PARENT_ID}-01`],
    ['a non-hex character in the parent-id', `00-${TRACE_ID}-00f067aa0ba902bz-01`],
    ['flags that are not hex', `00-${TRACE_ID}-${PARENT_ID}-0x`],
    ['wrong delimiters', `00_${TRACE_ID}_${PARENT_ID}_01`],
    ['a short higher version', `cc-${TRACE_ID}-${PARENT_ID}`],
    ['a higher version with no dash after the flags', `cc-${TRACE_ID}-${PARENT_ID}-01x`],
  ])('ignores %s', (_name, header) => {
    expect(parseTraceparent(header)).toBeNull();
  });

  test('parses a higher version by position and ignores its unknown fields', () => {
    expect(parseTraceparent(`cc-${TRACE_ID}-${PARENT_ID}-01-what-the-future-will-be-like`)).toEqual({
      traceId: TRACE_ID,
      parentId: PARENT_ID,
      sampled: true,
    });
    expect(parseTraceparent(`01-${TRACE_ID}-${PARENT_ID}-00`)?.sampled).toBe(false);
  });
});

describe('formatTraceparent', { tags: ['@exercise'] }, () => {
  test('writes version 00 with only the sampled flag', () => {
    expect(formatTraceparent({ traceId: TRACE_ID, parentId: PARENT_ID, sampled: true })).toBe(SAMPLED);
    expect(formatTraceparent({ traceId: TRACE_ID, parentId: PARENT_ID, sampled: false })).toBe(NOT_SAMPLED);
  });

  test('round-trips through parseTraceparent, downgrading a higher version to 00', () => {
    const parsed = parseTraceparent(`cc-${TRACE_ID}-${PARENT_ID}-09-future`);
    expect(parsed).not.toBeNull();
    expect(formatTraceparent(parsed!)).toBe(SAMPLED);
  });
});

describe('continueTrace', { tags: ['@exercise'] }, () => {
  const ids = { newSpanId: () => 'b7ad6b7169203331', newTraceId: () => '0af7651916cd43dd8448eb211c80319c' };

  test('joins a valid incoming trace with a new span id and the same sampling decision', () => {
    expect(continueTrace(SAMPLED, ids)).toEqual({
      traceId: TRACE_ID,
      parentId: 'b7ad6b7169203331',
      sampled: true,
    });
    expect(continueTrace(NOT_SAMPLED, ids)).toEqual({
      traceId: TRACE_ID,
      parentId: 'b7ad6b7169203331',
      sampled: false,
    });
  });

  test('restarts the trace when the header is missing or invalid', () => {
    const restarted = {
      traceId: '0af7651916cd43dd8448eb211c80319c',
      parentId: 'b7ad6b7169203331',
      sampled: true,
    };
    expect(continueTrace(undefined, ids)).toEqual(restarted);
    expect(continueTrace(`00-${'0'.repeat(32)}-${PARENT_ID}-01`, ids)).toEqual(restarted);
    expect(continueTrace(undefined, { ...ids, sampleNewTrace: false }).sampled).toBe(false);
  });

  test('generates valid random ids by default', () => {
    const first = continueTrace(undefined);
    const second = continueTrace(SAMPLED);
    expect(first.traceId).toMatch(/^[0-9a-f]{32}$/);
    expect(first.parentId).toMatch(/^[0-9a-f]{16}$/);
    expect(second.traceId).toBe(TRACE_ID);
    expect(second.parentId).toMatch(/^[0-9a-f]{16}$/);
    expect(second.parentId).not.toBe(PARENT_ID);
    expect(parseTraceparent(formatTraceparent(first))).toEqual(first);
  });
});
