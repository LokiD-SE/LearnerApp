import { describe, expect, it } from 'vitest';
import {
  MAX_ATTEMPTS_KEPT,
  MAX_NOTES_CHARS,
  emptyState,
  exerciseOf,
  isLessonComplete,
  itemKey,
  markRead,
  markUnread,
  recordAttempt,
  setNotes,
  showHint,
  showSolution,
  startNewEncounter,
  toggleBookmark,
  visitLesson,
  type AttemptInput,
} from '../../src/store/state';
import { at, realIndex } from './helpers';

const lesson = realIndex().lessons.get('idempotency-keys')!;
const now = at('2026-10-01T09:00:00.000Z');
const input = (itemId: string, extra: Partial<AttemptInput> = {}): AttemptInput => {
  const exercise = lesson.exercises.find((e) => e.id === itemId)!;
  return {
    lesson,
    itemId,
    kind: 'exercise',
    concept: exercise.concept,
    skill: exercise.skill,
    score: 1,
    hintsUsed: 0,
    selfAssessed: false,
    firstTry: true,
    mode: 'lesson',
    ...extra,
  };
};

describe('progress state', () => {
  it('records a visit and remembers the last lesson', () => {
    const s = visitLesson(emptyState(), lesson.id, now);
    expect(s.lastLessonId).toBe(lesson.id);
    expect(s.lessons[lesson.id]).toMatchObject({
      firstVisitedAt: now.toISOString(),
      lastVisitedAt: now.toISOString(),
    });
    const later = visitLesson(s, lesson.id, at('2026-10-02T09:00:00.000Z'));
    expect(later.lessons[lesson.id]!.firstVisitedAt).toBe(now.toISOString());
  });

  it('marking read schedules the recall cards once, for tomorrow', () => {
    const s = markRead(emptyState(), lesson, now);
    const keys = lesson.recall.map((c) => itemKey(lesson.id, c.id));
    expect(Object.keys(s.reviews).sort()).toEqual(keys.sort());
    expect(s.reviews[keys[0]!]!.due).toBe('2026-10-02T09:00:00.000Z');
    const again = markRead(s, lesson, at('2026-10-05T09:00:00.000Z'));
    expect(again.reviews[keys[0]!]!.due).toBe('2026-10-02T09:00:00.000Z');
    expect(again.lessons[lesson.id]!.readAt).toBe(now.toISOString());
  });

  it('records an attempt with hint-adjusted credit and schedules a first try', () => {
    const s = recordAttempt(emptyState(), input('race-condition-debug', { hintsUsed: 2 }), now);
    const key = itemKey(lesson.id, 'race-condition-debug');
    expect(s.attempts).toHaveLength(1);
    expect(s.attempts[0]).toMatchObject({ score: 1, credit: 0.7, firstTry: true });
    expect(exerciseOf(s, key)).toMatchObject({ attempts: 1, lastScore: 1, lastCredit: 0.7 });
    // credit 0.7 is a partial answer: scheduled in box 1, reviewed once
    expect(s.reviews[key]).toMatchObject({ kind: 'exercise', box: 1, reviews: 1 });
  });

  it('does not move the schedule for a retry', () => {
    const key = itemKey(lesson.id, 'methods-idempotent');
    const first = recordAttempt(emptyState(), input('methods-idempotent', { score: 0 }), now);
    const retry = recordAttempt(first, input('methods-idempotent', { score: 1, firstTry: false }), now);
    expect(retry.reviews[key]).toEqual(first.reviews[key]);
    expect(exerciseOf(retry, key)).toMatchObject({ attempts: 2, lastScore: 0, lastCredit: 0 });
  });

  it('completes the lesson only when read and every required exercise is attempted', () => {
    let s = markRead(emptyState(), lesson, now);
    expect(isLessonComplete(s, lesson)).toBe(false);
    const required = lesson.exercises.filter((e) => e.required);
    for (const exercise of required.slice(0, -1)) s = recordAttempt(s, input(exercise.id, { score: 0 }), now);
    expect(s.lessons[lesson.id]!.completedAt).toBeUndefined();
    s = recordAttempt(s, input(required.at(-1)!.id, { score: 0 }), now);
    expect(s.lessons[lesson.id]!.completedAt).toBe(now.toISOString());
    expect(markUnread(s, lesson.id).lessons[lesson.id]!.completedAt).toBeUndefined();
  });

  it('keeps hints and solution per exercise, and a new encounter clears them', () => {
    const key = itemKey(lesson.id, 'methods-idempotent');
    let s = showHint(emptyState(), key, 2);
    s = showHint(s, key, 2);
    s = showHint(s, key, 2);
    expect(exerciseOf(s, key).hintsShown).toBe(2);
    s = showSolution(s, key);
    expect(exerciseOf(s, key).solutionShown).toBe(true);
    s = startNewEncounter(s, key);
    expect(exerciseOf(s, key)).toMatchObject({ hintsShown: 0, solutionShown: false });
  });

  it('toggles bookmarks and caps notes', () => {
    let s = toggleBookmark(emptyState(), lesson.id);
    expect(s.lessons[lesson.id]!.bookmarked).toBe(true);
    s = toggleBookmark(s, lesson.id);
    expect(s.lessons[lesson.id]!.bookmarked).toBe(false);
    s = setNotes(s, lesson.id, 'x'.repeat(MAX_NOTES_CHARS + 50));
    expect(s.lessons[lesson.id]!.notes).toHaveLength(MAX_NOTES_CHARS);
  });

  it('keeps only the most recent attempts', () => {
    let s = emptyState();
    s = {
      ...s,
      attempts: Array.from(
        { length: MAX_ATTEMPTS_KEPT },
        () => recordAttempt(emptyState(), input('methods-idempotent'), now).attempts[0]!,
      ),
    };
    s = recordAttempt(s, input('which-need-keys'), now);
    expect(s.attempts).toHaveLength(MAX_ATTEMPTS_KEPT);
    expect(s.attempts.at(-1)!.itemId).toBe('which-need-keys');
  });
});
