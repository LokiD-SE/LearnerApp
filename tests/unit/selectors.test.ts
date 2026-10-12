import { describe, expect, it } from 'vitest';
import { pathProgress, lessonStatus } from '../../src/store/selectors';
import { emptyState, markRead, recordAttempt, type ProgressState } from '../../src/store/state';
import { at, realIndex } from './helpers';

const index = realIndex();
const now = at('2026-10-01T09:00:00.000Z');
const corePath = index.curriculum.paths.find((p) => p.id === 'payments-qa-core')!;

/** Read a lesson and attempt every required exercise once (any score) - "completed". */
function complete(state: ProgressState, lessonId: string): ProgressState {
  const lesson = index.lessons.get(lessonId)!;
  let next = markRead(state, lesson, now);
  for (const exercise of lesson.exercises.filter((e) => e.required)) {
    next = recordAttempt(
      next,
      {
        lesson,
        itemId: exercise.id,
        kind: 'exercise',
        concept: exercise.concept,
        skill: exercise.skill,
        score: 0,
        hintsUsed: 0,
        selfAssessed: false,
        firstTry: true,
        mode: 'lesson',
      },
      now,
    );
  }
  return next;
}

describe('pathProgress', () => {
  it('starts at the first lesson of the core path', () => {
    const progress = pathProgress(index, emptyState(), corePath);
    expect(progress).toMatchObject({ total: 8, ready: 8, completed: 0 });
    expect(progress.next?.id).toBe('http-request-response-anatomy');
  });

  it('moves to the next unfinished lesson in path order, skipping completed ones', () => {
    let state = complete(emptyState(), 'http-request-response-anatomy');
    state = complete(state, 'payment-lifecycle-overview'); // completed out of order
    expect(lessonStatus(index, state, 'payment-lifecycle-overview')).toBe('completed');
    const progress = pathProgress(index, state, corePath);
    expect(progress.completed).toBe(2);
    expect(progress.next?.id).toBe('http-methods-safety-idempotency');
  });

  it('reports no next lesson for a path whose lessons are all planned', () => {
    const planned = [...index.refs.values()].filter((ref) => ref.planned).map((ref) => ref.id);
    const plannedPath = {
      id: 'planned',
      title: 'P',
      level: 'beginner' as const,
      summary: 'S',
      lessons: planned,
    };
    const progress = pathProgress(index, emptyState(), plannedPath);
    expect(progress).toMatchObject({ total: planned.length, ready: 0 });
    expect(progress.next).toBeUndefined();
  });

  it('skips planned lessons when suggesting the next one', () => {
    const automation = index.curriculum.paths.find((p) => p.id === 'automation-engineer')!;
    const progress = pathProgress(index, emptyState(), automation);
    expect(progress.ready).toBeGreaterThan(0);
    expect(progress.ready).toBeLessThan(progress.total);
    expect(progress.next?.planned).toBe(false);
    expect(progress.next?.id).toBe('java-types-and-variables');
  });
});
