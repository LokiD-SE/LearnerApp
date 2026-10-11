/**
 * Spaced repetition: a Leitner-style schedule. An item climbs a box after a good answer,
 * stays after a partial one and drops to box 1 after a miss. Higher boxes wait longer.
 */

/** Days to wait after landing in box 1, 2, 3 ... */
export const BOX_INTERVAL_DAYS = [1, 3, 7, 16, 35, 90] as const;
export const MAX_BOX = BOX_INTERVAL_DAYS.length;
export const GOOD_SCORE = 0.8;
export const PARTIAL_SCORE = 0.5;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface ReviewSchedule {
  /** 0 = scheduled but never reviewed; 1..MAX_BOX after a review. */
  box: number;
  due: string;
  lastReviewedAt?: string;
  reviews: number;
  lapses: number;
}

export const intervalDays = (box: number) => BOX_INTERVAL_DAYS[Math.min(Math.max(box, 1), MAX_BOX) - 1] ?? 1;

/** A new item, first due a day from now. */
export function introduce(now: Date): ReviewSchedule {
  return { box: 0, due: new Date(now.getTime() + DAY_MS).toISOString(), reviews: 0, lapses: 0 };
}

export function schedule(previous: ReviewSchedule | undefined, score: number, now: Date): ReviewSchedule {
  const prevBox = previous?.box ?? 0;
  let box: number;
  let lapses = previous?.lapses ?? 0;
  if (score >= GOOD_SCORE) box = Math.min(prevBox + 1, MAX_BOX);
  else if (score >= PARTIAL_SCORE) box = Math.max(prevBox, 1);
  else {
    box = 1;
    if (previous && previous.reviews > 0) lapses += 1;
  }
  return {
    box,
    due: new Date(now.getTime() + intervalDays(box) * DAY_MS).toISOString(),
    lastReviewedAt: now.toISOString(),
    reviews: (previous?.reviews ?? 0) + 1,
    lapses,
  };
}

export const isDue = (item: ReviewSchedule, now: Date) => new Date(item.due).getTime() <= now.getTime();

/**
 * Orders due items so consecutive items come from different concepts where possible
 * (interleaving): oldest-due first within a concept, concepts in order of their oldest item.
 */
export function interleave<T extends { concept: string; due: string }>(items: readonly T[]): T[] {
  const byConcept = new Map<string, T[]>();
  for (const item of [...items].sort((a, b) => a.due.localeCompare(b.due))) {
    const group = byConcept.get(item.concept) ?? [];
    group.push(item);
    byConcept.set(item.concept, group);
  }
  const groups = [...byConcept.values()];
  const result: T[] = [];
  for (let round = 0; result.length < items.length; round += 1) {
    for (const group of groups) {
      const item = group[round];
      if (item) result.push(item);
    }
  }
  return result;
}
