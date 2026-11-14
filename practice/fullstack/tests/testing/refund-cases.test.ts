import { isDeepStrictEqual } from 'node:util';
import { refundCases } from '../../exercises/testing/refund-cases.js';
import { decideRefund } from '../../exercises/testing/refund-rules.js';
import { refundMutants } from './refund-mutants.js';

describe('refund cases that catch bugs', { tags: ['@exercise'] }, () => {
  test('there are between 1 and 10 cases, with distinct names', () => {
    expect(refundCases.length, 'write at least one case').toBeGreaterThan(0);
    expect(refundCases.length, 'at most 10 cases - choose boundaries, not volume').toBeLessThanOrEqual(10);
    const names = refundCases.map((c) => c.name);
    expect(new Set(names).size, 'every case needs its own name').toBe(names.length);
  });

  test('every case passes against the real rules', () => {
    for (const c of refundCases) {
      expect(decideRefund(c.input), `case "${c.name}"`).toEqual(c.expected);
    }
  });

  test.each(refundMutants.map((m) => [m.bug, m] as const))('a case catches the bug: %s', (_bug, mutant) => {
    const caughtBy = refundCases.filter((c) => !isDeepStrictEqual(mutant.decide(c.input), c.expected));
    expect(
      caughtBy.map((c) => c.name),
      'no case gives a different answer for this broken version - add a case on the boundary it breaks',
    ).not.toEqual([]);
  });
});
