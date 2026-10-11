import { describe, expect, it } from 'vitest';
import { BOX_INTERVAL_DAYS, MAX_BOX, interleave, introduce, isDue, schedule } from '../../src/domain/srs';
import { at, days } from './helpers';

const now = at('2026-10-01T09:00:00.000Z');
const dueIn = (due: string) => (Date.parse(due) - now.getTime()) / days(1);

describe('schedule', () => {
  it('a new item answered well goes to box 1, due in 1 day', () => {
    const next = schedule(undefined, 1, now);
    expect(next).toMatchObject({ box: 1, reviews: 1, lapses: 0 });
    expect(dueIn(next.due)).toBe(BOX_INTERVAL_DAYS[0]);
  });
  it('climbs one box per good answer, up to the last box', () => {
    let item = schedule(undefined, 1, now);
    for (let i = 0; i < 10; i += 1) item = schedule(item, 0.9, now);
    expect(item.box).toBe(MAX_BOX);
    expect(dueIn(item.due)).toBe(BOX_INTERVAL_DAYS[MAX_BOX - 1]);
  });
  it('stays in its box after a partial answer', () => {
    const box3 = { box: 3, due: now.toISOString(), reviews: 3, lapses: 0 };
    expect(schedule(box3, 0.6, now).box).toBe(3);
  });
  it('drops to box 1 and counts a lapse after a miss', () => {
    const box4 = { box: 4, due: now.toISOString(), reviews: 4, lapses: 1 };
    const next = schedule(box4, 0.2, now);
    expect(next).toMatchObject({ box: 1, lapses: 2, reviews: 5 });
  });
  it('a first answer that misses is not a lapse', () => {
    expect(schedule(undefined, 0, now).lapses).toBe(0);
  });
});

describe('introduce and isDue', () => {
  it('a new item is due one day later, not now', () => {
    const item = introduce(now);
    expect(item.box).toBe(0);
    expect(isDue(item, now)).toBe(false);
    expect(isDue(item, new Date(now.getTime() + days(1)))).toBe(true);
  });
});

describe('interleave', () => {
  it('alternates concepts, oldest due first within each', () => {
    const items = [
      { id: 'a1', concept: 'a', due: '2026-01-01' },
      { id: 'a2', concept: 'a', due: '2026-01-02' },
      { id: 'a3', concept: 'a', due: '2026-01-03' },
      { id: 'b1', concept: 'b', due: '2026-01-05' },
      { id: 'c1', concept: 'c', due: '2026-01-04' },
    ];
    expect(interleave(items).map((i) => i.id)).toEqual(['a1', 'c1', 'b1', 'a2', 'a3']);
  });
  it('handles an empty list', () => {
    expect(interleave([])).toEqual([]);
  });
});
