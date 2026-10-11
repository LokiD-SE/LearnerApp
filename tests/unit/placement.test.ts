import { describe, expect, it } from 'vitest';
import { lessonStatus, pathProgress, placementItems } from '../../src/store/selectors';
import {
  clearPlacement,
  emptyState,
  itemKey,
  markRead,
  recordAttempt,
  recordPlacement,
} from '../../src/store/state';
import { STORAGE_KEY, loadProgress } from '../../src/store/storage';
import { parseHash, href } from '../../src/ui/router';
import { at, memoryStore, realIndex } from './helpers';

const index = realIndex();
const now = at('2026-10-01T09:00:00.000Z');
const anatomy = index.lessons.get('http-request-response-anatomy')!;
const corePath = index.curriculum.paths.find((p) => p.id === 'payments-qa-core')!;
const allRight = (lesson = anatomy) => lesson.placement.map((q) => ({ questionId: q.id, score: 1 }));

describe('recordPlacement', () => {
  it('tests out only when every placement question is fully correct', () => {
    const s = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    expect(s.placements[anatomy.id]).toMatchObject({
      result: 'tested-out',
      correct: anatomy.placement.length,
      source: 'path',
    });
  });

  it('recommends study when any answer is wrong, partly right or "don\'t know"', () => {
    const partly = allRight().map((a, i) => (i === 0 ? { ...a, score: 0.5 } : a));
    const s = recordPlacement(emptyState(), anatomy, partly, 'lesson', now);
    expect(s.placements[anatomy.id]).toMatchObject({
      result: 'study',
      correct: anatomy.placement.length - 1,
    });
    const missing = recordPlacement(emptyState(), anatomy, allRight().slice(1), 'lesson', now);
    expect(missing.placements[anatomy.id]!.result).toBe('study');
  });

  it('puts the recall cards of a tested-out lesson into the review queue, and only then', () => {
    const passed = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    expect(Object.keys(passed.reviews)).toHaveLength(anatomy.recall.length);
    expect(passed.reviews[itemKey(anatomy.id, anatomy.recall[0]!.id)]!.due).toBe('2026-10-02T09:00:00.000Z');
    const failed = recordPlacement(emptyState(), anatomy, [], 'path', now);
    expect(Object.keys(failed.reviews)).toHaveLength(0);
  });

  it('is not mastery evidence', () => {
    const s = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    expect(s.attempts).toEqual([]);
  });

  it('a retake replaces the earlier result, and "study it anyway" clears it', () => {
    let s = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    s = recordPlacement(s, anatomy, [], 'lesson', at('2026-10-03T09:00:00.000Z'));
    expect(s.placements[anatomy.id]).toMatchObject({ result: 'study', source: 'lesson' });
    expect(clearPlacement(s, anatomy.id).placements[anatomy.id]).toBeUndefined();
  });
});

describe('placement in lesson status and path progress', () => {
  it('shows tested out, but completing the lesson outranks it', () => {
    let s = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    expect(lessonStatus(index, s, anatomy.id)).toBe('tested-out');
    s = markRead(s, anatomy, now);
    for (const e of anatomy.exercises.filter((x) => x.required)) {
      s = recordAttempt(
        s,
        {
          lesson: anatomy,
          itemId: e.id,
          kind: 'exercise',
          concept: e.concept,
          skill: e.skill,
          score: 1,
          hintsUsed: 0,
          selfAssessed: false,
          firstTry: true,
          mode: 'lesson',
        },
        now,
      );
    }
    expect(lessonStatus(index, s, anatomy.id)).toBe('completed');
  });

  it('skips tested-out lessons when choosing the next lesson on a path', () => {
    const s = recordPlacement(emptyState(), anatomy, allRight(), 'path', now);
    const progress = pathProgress(index, s, corePath);
    expect(progress).toMatchObject({ completed: 0, testedOut: 1 });
    expect(progress.next?.id).toBe('http-methods-safety-idempotency');
  });

  it('collects placement questions for a path in path order, or for one lesson', () => {
    const forPath = placementItems(index, { kind: 'path', id: corePath.id });
    expect(forPath[0]!.lesson.id).toBe(corePath.lessons[0]);
    expect(new Set(forPath.map((i) => i.lesson.id)).size).toBe(corePath.lessons.length);
    expect(placementItems(index, { kind: 'lesson', id: anatomy.id })).toHaveLength(anatomy.placement.length);
    expect(placementItems(index, { kind: 'path', id: 'no-such-path' })).toEqual([]);
  });
});

describe('compatibility and routing', () => {
  it('loads progress saved before placements existed', () => {
    const old = { version: 1, lessons: {}, exercises: {}, reviews: {}, attempts: [] };
    const result = loadProgress(memoryStore({ [STORAGE_KEY]: JSON.stringify(old) }), now);
    expect(result.warning).toBeUndefined();
    expect(result.state.placements).toEqual({});
  });

  it('parses placement routes', () => {
    expect(parseHash('#/placement/path/payments-qa-core')).toEqual({
      name: 'placement',
      kind: 'path',
      id: 'payments-qa-core',
    });
    expect(parseHash(href.placement('lesson', 'idempotency-keys'))).toEqual({
      name: 'placement',
      kind: 'lesson',
      id: 'idempotency-keys',
    });
    expect(parseHash('#/placement/stage/x').name).toBe('not-found');
  });
});
