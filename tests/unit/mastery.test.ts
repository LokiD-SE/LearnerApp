import { describe, expect, it } from 'vitest';
import { conceptMastery, type ConceptItem, type Evidence } from '../../src/domain/mastery';
import { days } from './helpers';

const items: ConceptItem[] = [
  { key: 'l/mcq', skill: 'recognition' },
  { key: 'l/explain', skill: 'recall' },
  { key: 'l/debug', skill: 'application' },
];
const t0 = Date.parse('2026-10-01T09:00:00.000Z');
const ev = (key: string, credit: number, extra: Partial<Evidence> = {}): Evidence => ({
  key,
  skill: items.find((i) => i.key === key)!.skill,
  credit,
  selfAssessed: false,
  mode: 'lesson',
  at: new Date(t0).toISOString(),
  firstTry: true,
  ...extra,
});

describe('conceptMastery', () => {
  it('is not started without evidence', () => {
    expect(conceptMastery(items, []).level).toBe('not-started');
  });

  it('one right multiple-choice answer is not mastery', () => {
    const m = conceptMastery(items, [ev('l/mcq', 1)]);
    expect(m.score).toBe(1);
    expect(m.coverage).toBeCloseTo(1 / 6, 3);
    expect(m.level).toBe('practising');
  });

  it('a high score without a passed practical exercise stays below proficient', () => {
    const m = conceptMastery(items, [ev('l/mcq', 1), ev('l/explain', 1), ev('l/debug', 0.5)]);
    expect(m.practical).toBe(false);
    expect(m.level).toBe('practising');
  });

  it('is proficient with high weighted score, coverage and a practical success', () => {
    const m = conceptMastery(items, [ev('l/mcq', 1), ev('l/explain', 0.75), ev('l/debug', 1)]);
    expect(m.score).toBeGreaterThanOrEqual(0.8);
    expect(m.practical).toBe(true);
    expect(m.retained).toBe(false);
    expect(m.level).toBe('proficient');
  });

  it('becomes mastered only after a good review at least a day after first evidence', () => {
    const base = [ev('l/mcq', 1), ev('l/explain', 1), ev('l/debug', 1)];
    const tooSoon = ev('l/debug', 1, { mode: 'review', at: new Date(t0 + days(0.5)).toISOString() });
    expect(conceptMastery(items, [...base, tooSoon]).level).toBe('proficient');
    const later = ev('l/debug', 1, { mode: 'review', at: new Date(t0 + days(2)).toISOString() });
    expect(conceptMastery(items, [...base, later]).level).toBe('mastered');
  });

  it('ignores retries straight after feedback', () => {
    const m = conceptMastery(items, [
      ev('l/debug', 0),
      ev('l/debug', 1, { firstTry: false, at: new Date(t0 + 1000).toISOString() }),
    ]);
    expect(m.score).toBe(0);
    expect(m.level).toBe('attempted');
  });

  it('uses the latest first-try evidence per item', () => {
    const m = conceptMastery(items, [
      ev('l/debug', 0),
      ev('l/debug', 1, { mode: 'review', at: new Date(t0 + days(3)).toISOString() }),
    ]);
    expect(m.score).toBe(1);
  });

  it('weighs practical evidence more than recognition', () => {
    const recognitionRight = conceptMastery(items, [ev('l/mcq', 1), ev('l/debug', 0)]);
    const practicalRight = conceptMastery(items, [ev('l/mcq', 0), ev('l/debug', 1)]);
    expect(practicalRight.score).toBeGreaterThan(recognitionRight.score);
  });

  it('counts self-assessed evidence a little less', () => {
    const auto = conceptMastery(items, [ev('l/mcq', 0), ev('l/explain', 1)]);
    const self = conceptMastery(items, [ev('l/mcq', 0), ev('l/explain', 1, { selfAssessed: true })]);
    expect(self.score).toBeLessThan(auto.score);
  });

  it('ignores evidence for items that are not part of the concept', () => {
    expect(conceptMastery(items, [{ ...ev('l/mcq', 1), key: 'other/x' }]).level).toBe('not-started');
  });
});
