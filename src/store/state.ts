/**
 * Learner progress: what has been read, attempted, scheduled and noted.
 *
 * The state is plain JSON (stored in localStorage, exportable as a file) and every change
 * goes through a pure function here, so the rules are unit-testable without a browser.
 */
import { z } from 'zod';
import { SKILLS } from '../content/schema';
import type { Lesson, Skill } from '../content/schema';
import { creditFor } from '../domain/grading';
import { introduce, schedule, type ReviewSchedule } from '../domain/srs';

export const STATE_VERSION = 1;
export const MAX_ATTEMPTS_KEPT = 2000;
export const MAX_RESPONSE_CHARS = 4000;
export const MAX_NOTES_CHARS = 20000;

const IsoDate = z.string().refine((value) => !Number.isNaN(Date.parse(value)), 'not an ISO date');
const Score = z.number().min(0).max(1);

const AttemptSchema = z.object({
  lessonId: z.string(),
  itemId: z.string(),
  kind: z.enum(['exercise', 'recall']),
  concept: z.string(),
  skill: z.enum(SKILLS),
  score: Score,
  credit: Score,
  hintsUsed: z.number().int().min(0),
  selfAssessed: z.boolean(),
  firstTry: z.boolean(),
  mode: z.enum(['lesson', 'review']),
  at: IsoDate,
  response: z.string().max(MAX_RESPONSE_CHARS).optional(),
});

const ExerciseStateSchema = z.object({
  hintsShown: z.number().int().min(0).default(0),
  solutionShown: z.boolean().default(false),
  draft: z.string().max(MAX_RESPONSE_CHARS).optional(),
  attempts: z.number().int().min(0).default(0),
  lastScore: Score.optional(),
  lastCredit: Score.optional(),
  lastAt: IsoDate.optional(),
  lastResponse: z.string().max(MAX_RESPONSE_CHARS).optional(),
});

const LessonStateSchema = z.object({
  firstVisitedAt: IsoDate.optional(),
  lastVisitedAt: IsoDate.optional(),
  readAt: IsoDate.optional(),
  completedAt: IsoDate.optional(),
  bookmarked: z.boolean().default(false),
  notes: z.string().max(MAX_NOTES_CHARS).default(''),
});

const ReviewEntrySchema = z.object({
  lessonId: z.string(),
  itemId: z.string(),
  kind: z.enum(['exercise', 'recall']),
  concept: z.string(),
  box: z.number().int().min(0),
  due: IsoDate,
  lastReviewedAt: IsoDate.optional(),
  reviews: z.number().int().min(0),
  lapses: z.number().int().min(0),
});

export const ProgressStateSchema = z.object({
  version: z.literal(STATE_VERSION),
  lastLessonId: z.string().optional(),
  lessons: z.record(z.string(), LessonStateSchema).default({}),
  exercises: z.record(z.string(), ExerciseStateSchema).default({}),
  reviews: z.record(z.string(), ReviewEntrySchema).default({}),
  attempts: z.array(AttemptSchema).default([]),
});

export type Attempt = z.infer<typeof AttemptSchema>;
export type ExerciseState = z.infer<typeof ExerciseStateSchema>;
export type LessonState = z.infer<typeof LessonStateSchema>;
export type ReviewEntry = z.infer<typeof ReviewEntrySchema>;
export type ProgressState = z.infer<typeof ProgressStateSchema>;

/** Exercises and recall cards are keyed by lesson so ids only need to be unique per lesson. */
export const itemKey = (lessonId: string, itemId: string) => `${lessonId}/${itemId}`;

export const emptyState = (): ProgressState => ({
  version: STATE_VERSION,
  lessons: {},
  exercises: {},
  reviews: {},
  attempts: [],
});

const emptyLesson = (): LessonState => ({ bookmarked: false, notes: '' });
const emptyExercise = (): ExerciseState => ({ hintsShown: 0, solutionShown: false, attempts: 0 });

const lessonOf = (state: ProgressState, lessonId: string) => state.lessons[lessonId] ?? emptyLesson();
export const exerciseOf = (state: ProgressState, key: string) => state.exercises[key] ?? emptyExercise();

function withLesson(state: ProgressState, lessonId: string, patch: Partial<LessonState>): ProgressState {
  return { ...state, lessons: { ...state.lessons, [lessonId]: { ...lessonOf(state, lessonId), ...patch } } };
}

function withExercise(state: ProgressState, key: string, patch: Partial<ExerciseState>): ProgressState {
  return { ...state, exercises: { ...state.exercises, [key]: { ...exerciseOf(state, key), ...patch } } };
}

export function visitLesson(state: ProgressState, lessonId: string, now: Date): ProgressState {
  const current = lessonOf(state, lessonId);
  const at = now.toISOString();
  return {
    ...withLesson(state, lessonId, { firstVisitedAt: current.firstVisitedAt ?? at, lastVisitedAt: at }),
    lastLessonId: lessonId,
  };
}

/** Reading a lesson puts its recall cards into the review queue (first due tomorrow). */
export function markRead(state: ProgressState, lesson: Lesson, now: Date): ProgressState {
  let next = withLesson(state, lesson.id, { readAt: lessonOf(state, lesson.id).readAt ?? now.toISOString() });
  const reviews = { ...next.reviews };
  for (const card of lesson.recall) {
    const key = itemKey(lesson.id, card.id);
    if (!reviews[key]) {
      reviews[key] = {
        lessonId: lesson.id,
        itemId: card.id,
        kind: 'recall',
        concept: card.concept,
        ...introduce(now),
      };
    }
  }
  next = { ...next, reviews };
  return updateCompletion(next, lesson, now);
}

export function markUnread(state: ProgressState, lessonId: string): ProgressState {
  return withLesson(state, lessonId, { readAt: undefined, completedAt: undefined });
}

export function toggleBookmark(state: ProgressState, lessonId: string): ProgressState {
  return withLesson(state, lessonId, { bookmarked: !lessonOf(state, lessonId).bookmarked });
}

export function setNotes(state: ProgressState, lessonId: string, notes: string): ProgressState {
  return withLesson(state, lessonId, { notes: notes.slice(0, MAX_NOTES_CHARS) });
}

export function showHint(state: ProgressState, key: string, totalHints: number): ProgressState {
  const current = exerciseOf(state, key);
  return withExercise(state, key, { hintsShown: Math.min(current.hintsShown + 1, totalHints) });
}

export function showSolution(state: ProgressState, key: string): ProgressState {
  return withExercise(state, key, { solutionShown: true });
}

export function saveDraft(state: ProgressState, key: string, draft: string): ProgressState {
  return withExercise(state, key, { draft: draft.slice(0, MAX_RESPONSE_CHARS) });
}

/** "Try again" later: a fresh encounter with no hints or solution showing. */
export function startNewEncounter(state: ProgressState, key: string): ProgressState {
  return withExercise(state, key, { hintsShown: 0, solutionShown: false, draft: undefined });
}

export interface AttemptInput {
  lesson: Lesson;
  itemId: string;
  kind: 'exercise' | 'recall';
  concept: string;
  skill: Skill;
  /** raw score before the hint penalty, 0..1 */
  score: number;
  hintsUsed: number;
  selfAssessed: boolean;
  firstTry: boolean;
  mode: 'lesson' | 'review';
  response?: string;
}

export function recordAttempt(state: ProgressState, input: AttemptInput, now: Date): ProgressState {
  const key = itemKey(input.lesson.id, input.itemId);
  const credit = creditFor(input.score, input.hintsUsed);
  const at = now.toISOString();
  const response = input.response?.slice(0, MAX_RESPONSE_CHARS);
  const attempt: Attempt = {
    lessonId: input.lesson.id,
    itemId: input.itemId,
    kind: input.kind,
    concept: input.concept,
    skill: input.skill,
    score: Math.min(1, Math.max(0, input.score)),
    credit,
    hintsUsed: input.hintsUsed,
    selfAssessed: input.selfAssessed,
    firstTry: input.firstTry,
    mode: input.mode,
    at,
    ...(response === undefined ? {} : { response }),
  };

  let next: ProgressState = { ...state, attempts: [...state.attempts, attempt].slice(-MAX_ATTEMPTS_KEPT) };
  const current = exerciseOf(next, key);
  // The "last result" shown to the learner is the last first try - the same evidence the
  // mastery model uses - so an immediate retry after feedback cannot inflate it.
  next = withExercise(next, key, {
    attempts: current.attempts + 1,
    ...(input.firstTry ? { lastScore: attempt.score, lastCredit: credit, lastAt: at } : {}),
    ...(response === undefined ? {} : { lastResponse: response }),
  });

  // Only a first try moves the review schedule; an immediate retry after feedback says
  // little about what will be remembered next week.
  if (input.firstTry) {
    const previous = next.reviews[key];
    const scheduled: ReviewSchedule = schedule(previous, credit, now);
    next = {
      ...next,
      reviews: {
        ...next.reviews,
        [key]: {
          lessonId: input.lesson.id,
          itemId: input.itemId,
          kind: input.kind,
          concept: input.concept,
          ...scheduled,
        },
      },
    };
  }
  return updateCompletion(next, input.lesson, now);
}

/** A lesson is completed once it has been read and every required exercise attempted. */
export function isLessonComplete(state: ProgressState, lesson: Lesson): boolean {
  if (!lessonOf(state, lesson.id).readAt) return false;
  return lesson.exercises
    .filter((exercise) => exercise.required)
    .every((exercise) => exerciseOf(state, itemKey(lesson.id, exercise.id)).attempts > 0);
}

function updateCompletion(state: ProgressState, lesson: Lesson, now: Date): ProgressState {
  const current = lessonOf(state, lesson.id);
  if (current.completedAt || !isLessonComplete(state, lesson)) return state;
  return withLesson(state, lesson.id, { completedAt: now.toISOString() });
}
