import { describe, expect, it } from 'vitest';
import { RECENT_MS, buildPracticeSession, remediationFor } from '../../src/store/adaptive';
import { masteryOf } from '../../src/store/selectors';
import {
  emptyState,
  recordAttempt,
  visitLesson,
  type AttemptInput,
  type ProgressState,
} from '../../src/store/state';
import { href, parseHash } from '../../src/ui/router';
import { at, days, realIndex } from './helpers';

const index = realIndex();
const lesson = index.lessons.get('idempotency-keys')!;
const T0 = at('2026-10-01T09:00:00.000Z');
const later = (ms: number) => new Date(T0.getTime() + ms);
const exercise = (id: string) => lesson.exercises.find((e) => e.id === id)!;

function answer(
  state: ProgressState,
  itemId: string,
  score: number,
  when: Date,
  extra: Partial<AttemptInput> = {},
) {
  const ex = lesson.exercises.find((e) => e.id === itemId);
  const card = lesson.recall.find((c) => c.id === itemId);
  return recordAttempt(
    state,
    {
      lesson,
      itemId,
      kind: ex ? 'exercise' : 'recall',
      concept: (ex ?? card)!.concept,
      skill: ex ? ex.skill : 'recall',
      score,
      hintsUsed: 0,
      selfAssessed: !ex || ['short', 'testdesign', 'interview'].includes(ex.type),
      firstTry: true,
      mode: 'lesson',
      ...extra,
    },
    when,
  );
}

describe('remediationFor', () => {
  it('suggests the most specific sections for the concept, in lesson order', () => {
    const { sections } = remediationFor(lesson, exercise('methods-idempotent'), emptyState());
    expect(sections.map((s) => s.id)).toEqual(['intuition', 'what']);
  });

  it('suggests an untried sibling exercise on the same concept, then the weakest', () => {
    expect(remediationFor(lesson, exercise('methods-idempotent'), emptyState()).sibling?.id).toBe(
      'which-need-keys',
    );
    const tried = answer(emptyState(), 'which-need-keys', 0.4, T0);
    expect(remediationFor(lesson, exercise('methods-idempotent'), tried).sibling?.id).toBe(
      'retry-same-key-explain',
    );
  });

  it('points a diagnosis exercise at the sections about diagnosis', () => {
    const { sections, sibling } = remediationFor(lesson, exercise('duplicate-charge-rca'), emptyState());
    expect(sections.map((s) => s.id)).toEqual(['example', 'mistakes']);
    expect(sibling?.id).toBe('interview-refund-idempotency');
  });
});

describe('buildPracticeSession', () => {
  it('is empty until a lesson has been opened', () => {
    expect(buildPracticeSession(index, emptyState(), T0)).toEqual([]);
  });

  it('starts an opened lesson with one practical, auto-graded item per untried concept', () => {
    const state = visitLesson(emptyState(), lesson.id, T0);
    const session = buildPracticeSession(index, state, T0);
    expect(session.map((i) => i.exercise.id)).toEqual([
      'which-need-keys',
      'race-condition-debug',
      'duplicate-charge-rca',
    ]);
    expect(session.every((i) => i.reason === 'Not practised yet')).toBe(true);
  });

  it('pushes a recognised-but-not-applied concept to the front, with practical items first', () => {
    let state = visitLesson(emptyState(), lesson.id, T0);
    state = answer(state, 'methods-idempotent', 1, T0);
    const session = buildPracticeSession(index, state, later(RECENT_MS + 1000));
    expect(session[0]).toMatchObject({
      conceptId: 'idempotent-operations',
      reason: 'You recognise this - now show you can apply it',
    });
    expect(session[0]!.exercise.id).toBe('which-need-keys');
    // the urgent concept gets a second item, but never two in a row from the same concept
    expect(session.filter((i) => i.conceptId === 'idempotent-operations')).toHaveLength(2);
    for (let i = 1; i < session.length; i += 1) {
      expect(session[i]!.conceptId).not.toBe(session[i - 1]!.conceptId);
    }
  });

  it('leaves out items answered in the last few minutes', () => {
    let state = visitLesson(emptyState(), lesson.id, T0);
    state = answer(state, 'which-need-keys', 0, T0);
    const soon = buildPracticeSession(index, state, later(60 * 1000)).map((i) => i.exercise.id);
    expect(soon).not.toContain('which-need-keys');
    const afterwards = buildPracticeSession(index, state, later(RECENT_MS + 1000)).map((i) => i.exercise.id);
    expect(afterwards).toContain('which-need-keys');
  });

  it('leaves out mastered concepts', () => {
    let state = visitLesson(emptyState(), lesson.id, T0);
    for (const id of [
      'duplicate-charge-rca',
      'interview-refund-idempotency',
      'recall-different-keys',
      'recall-same-key',
    ]) {
      state = answer(state, id, 1, T0);
    }
    state = answer(state, 'duplicate-charge-rca', 1, later(days(2)), { mode: 'review' });
    expect(masteryOf(lesson, 'duplicate-payment-diagnosis', state).level).toBe('mastered');
    const session = buildPracticeSession(index, state, later(days(3)));
    expect(session.some((i) => i.conceptId === 'duplicate-payment-diagnosis')).toBe(false);
  });

  it('can be scoped to one lesson, even one not opened yet, and respects the size', () => {
    let state = visitLesson(emptyState(), lesson.id, T0);
    state = answer(state, 'methods-idempotent', 0, T0);
    const scoped = buildPracticeSession(index, state, later(days(1)), {
      lessonId: 'payment-lifecycle-overview',
    });
    expect(scoped.length).toBeGreaterThan(0);
    expect(scoped.every((i) => i.lesson.id === 'payment-lifecycle-overview')).toBe(true);
    expect(buildPracticeSession(index, state, later(days(1)), { size: 2 })).toHaveLength(2);
  });

  it('counts a practice answer a day later as retention', () => {
    let state = visitLesson(emptyState(), lesson.id, T0);
    for (const id of [
      'duplicate-charge-rca',
      'interview-refund-idempotency',
      'recall-different-keys',
      'recall-same-key',
    ]) {
      state = answer(state, id, 1, T0);
    }
    expect(masteryOf(lesson, 'duplicate-payment-diagnosis', state).level).toBe('proficient');
    state = answer(state, 'duplicate-charge-rca', 1, later(days(1) + 1000), { mode: 'practice' });
    expect(masteryOf(lesson, 'duplicate-payment-diagnosis', state).level).toBe('mastered');
  });
});

describe('routes for adaptive practice', () => {
  it('parses lesson focus targets and ignores anything else', () => {
    expect(parseHash(href.lesson('idempotency-keys', 'section-why'))).toEqual({
      name: 'lesson',
      id: 'idempotency-keys',
      focus: 'section-why',
    });
    expect(parseHash('#/lesson/idempotency-keys?focus=exercise-race-condition-debug')).toMatchObject({
      focus: 'exercise-race-condition-debug',
    });
    expect(parseHash('#/lesson/idempotency-keys?focus=javascript:alert(1)')).toEqual({
      name: 'lesson',
      id: 'idempotency-keys',
    });
  });
  it('parses practice routes', () => {
    expect(parseHash('#/practice')).toEqual({ name: 'practice' });
    expect(parseHash(href.practice('idempotency-keys'))).toEqual({
      name: 'practice',
      lesson: 'idempotency-keys',
    });
  });
});
