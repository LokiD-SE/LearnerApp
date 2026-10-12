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
export const MAX_INTERVIEWS_KEPT = 30;
export const MAX_INTERVIEW_ATTEMPTS_KEPT = 12;
export const MAX_INTERVIEW_RESPONSE_CHARS = 2000;

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
  mode: z.enum(['lesson', 'review', 'practice']),
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

const PlacementResultSchema = z.object({
  /** 'tested-out' only when every placement question of the lesson was answered fully correctly */
  result: z.enum(['tested-out', 'study']),
  at: IsoDate,
  correct: z.number().int().min(0),
  total: z.number().int().min(1),
  /** a whole learning path's placement test, or one lesson's "test out" */
  source: z.enum(['path', 'lesson']),
  /** question id -> score (0..1); "I don't know" is 0 */
  answers: z.record(z.string(), Score).default({}),
});

const InterviewAnswerSchema = z.object({
  /** raw score before the hint penalty */
  score: Score,
  credit: Score,
  hintsUsed: z.number().int().min(0),
  selfAssessed: z.boolean(),
  /** rubric points the answer did not cover (indexes into the rubric), for feedback */
  missed: z.array(z.number().int().min(0)).default([]),
  response: z.string().max(MAX_INTERVIEW_RESPONSE_CHARS).optional(),
  at: IsoDate,
});

const InterviewRoundAttemptSchema = z.object({
  startedAt: IsoDate,
  finishedAt: IsoDate.optional(),
  /** question key -> hints shown before answering */
  hints: z.record(z.string(), z.number().int().min(0)).default({}),
  /** question key -> the answer; only the first answer in an attempt counts */
  answers: z.record(z.string(), InterviewAnswerSchema).default({}),
});

const InterviewAttemptSchema = z.object({
  startedAt: IsoDate,
  /** round index (as a string) -> that round in this attempt; rounds can be taken in any order */
  rounds: z.record(z.string(), InterviewRoundAttemptSchema).default({}),
});

/** A generated practice interview: fixed rounds and questions, taken any number of times. */
const MockInterviewSchema = z.object({
  id: z.string(),
  course: z.object({ kind: z.enum(['path', 'subject']), id: z.string() }),
  /** the company profile in content/interviews/interviews.yaml */
  profileId: z.string(),
  seed: z.number().int(),
  createdAt: IsoDate,
  rounds: z.array(
    z.object({
      type: z.string(),
      label: z.string(),
      /** question keys: bank:<id> or lesson:<lessonId>/<exerciseId> */
      questions: z.array(z.string()),
    }),
  ),
  attempts: z.array(InterviewAttemptSchema).default([]),
});

export const ProgressStateSchema = z.object({
  version: z.literal(STATE_VERSION),
  lastLessonId: z.string().optional(),
  lessons: z.record(z.string(), LessonStateSchema).default({}),
  exercises: z.record(z.string(), ExerciseStateSchema).default({}),
  reviews: z.record(z.string(), ReviewEntrySchema).default({}),
  attempts: z.array(AttemptSchema).default([]),
  // Added after version 1 shipped; the default keeps older saved progress loading unchanged.
  placements: z.record(z.string(), PlacementResultSchema).default({}),
  // Also added after version 1 shipped, the same way. Oldest first.
  interviews: z.array(MockInterviewSchema).default([]),
});

export type Attempt = z.infer<typeof AttemptSchema>;
export type ExerciseState = z.infer<typeof ExerciseStateSchema>;
export type LessonState = z.infer<typeof LessonStateSchema>;
export type ReviewEntry = z.infer<typeof ReviewEntrySchema>;
export type PlacementResult = z.infer<typeof PlacementResultSchema>;
export type ProgressState = z.infer<typeof ProgressStateSchema>;
export type MockInterview = z.infer<typeof MockInterviewSchema>;
export type InterviewAttempt = z.infer<typeof InterviewAttemptSchema>;
export type InterviewRoundAttempt = z.infer<typeof InterviewRoundAttemptSchema>;
export type InterviewAnswer = z.infer<typeof InterviewAnswerSchema>;

/** Exercises and recall cards are keyed by lesson so ids only need to be unique per lesson. */
export const itemKey = (lessonId: string, itemId: string) => `${lessonId}/${itemId}`;

export const emptyState = (): ProgressState => ({
  version: STATE_VERSION,
  lessons: {},
  exercises: {},
  reviews: {},
  attempts: [],
  placements: {},
  interviews: [],
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

/** Puts a lesson's recall cards into the review queue (first due tomorrow), once. */
function scheduleRecallCards(state: ProgressState, lesson: Lesson, now: Date): ProgressState {
  const reviews = { ...state.reviews };
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
  return { ...state, reviews };
}

/** Reading a lesson puts its recall cards into the review queue (first due tomorrow). */
export function markRead(state: ProgressState, lesson: Lesson, now: Date): ProgressState {
  const next = withLesson(state, lesson.id, {
    readAt: lessonOf(state, lesson.id).readAt ?? now.toISOString(),
  });
  return updateCompletion(scheduleRecallCards(next, lesson, now), lesson, now);
}

export interface PlacementAnswer {
  questionId: string;
  /** 0..1; "I don't know" is 0 */
  score: number;
}

/**
 * Records a lesson's placement result. Testing out needs every placement question answered
 * fully correctly; a tested-out lesson's recall cards join the review queue, so retention is
 * still checked. Placement answers are not mastery evidence (docs/MASTERY_MODEL.md).
 */
export function recordPlacement(
  state: ProgressState,
  lesson: Lesson,
  answers: readonly PlacementAnswer[],
  source: PlacementResult['source'],
  now: Date,
): ProgressState {
  const total = lesson.placement.length;
  if (total === 0) return state;
  const scores = new Map(answers.map((a) => [a.questionId, Math.min(1, Math.max(0, a.score))]));
  const correct = lesson.placement.filter((q) => scores.get(q.id) === 1).length;
  const result: PlacementResult = {
    result: correct === total ? 'tested-out' : 'study',
    at: now.toISOString(),
    correct,
    total,
    source,
    answers: Object.fromEntries(lesson.placement.map((q) => [q.id, scores.get(q.id) ?? 0])),
  };
  const next = { ...state, placements: { ...state.placements, [lesson.id]: result } };
  return result.result === 'tested-out' ? scheduleRecallCards(next, lesson, now) : next;
}

/** "Study it anyway": forget the placement result for a lesson. */
export function clearPlacement(state: ProgressState, lessonId: string): ProgressState {
  const placements = { ...state.placements };
  delete placements[lessonId];
  return { ...state, placements };
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
  mode: 'lesson' | 'review' | 'practice';
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

/* ------------------------------------------------------------------ interview practice */
/* Interview answers are practice for interviews, not mastery evidence (docs/MASTERY_MODEL.md):
 * they never touch attempts, reviews or lesson completion. */

function withInterview(
  state: ProgressState,
  id: string,
  change: (interview: MockInterview) => MockInterview,
): ProgressState {
  const index = state.interviews.findIndex((interview) => interview.id === id);
  if (index < 0) return state;
  const interviews = [...state.interviews];
  interviews[index] = change(interviews[index]!);
  return { ...state, interviews };
}

/** Changes one round of the interview's latest attempt; does nothing if that round isn't started. */
function withLatestRound(
  state: ProgressState,
  id: string,
  roundIndex: number,
  change: (round: InterviewRoundAttempt) => InterviewRoundAttempt,
): ProgressState {
  return withInterview(state, id, (interview) => {
    const attempt = interview.attempts.at(-1);
    const round = attempt?.rounds[String(roundIndex)];
    if (!attempt || !round) return interview;
    const attempts = [...interview.attempts];
    attempts[attempts.length - 1] = {
      ...attempt,
      rounds: { ...attempt.rounds, [roundIndex]: change(round) },
    };
    return { ...interview, attempts };
  });
}

/** Keeps the newest interviews when there are too many. */
export function addInterview(state: ProgressState, interview: MockInterview): ProgressState {
  return { ...state, interviews: [...state.interviews, interview].slice(-MAX_INTERVIEWS_KEPT) };
}

export function deleteInterview(state: ProgressState, id: string): ProgressState {
  return { ...state, interviews: state.interviews.filter((interview) => interview.id !== id) };
}

/** A fresh attempt at the same rounds and questions; the oldest attempts go when there are too many. */
export function startInterviewAttempt(state: ProgressState, id: string, now: Date): ProgressState {
  return withInterview(state, id, (interview) => ({
    ...interview,
    attempts: [...interview.attempts, { startedAt: now.toISOString(), rounds: {} }].slice(
      -MAX_INTERVIEW_ATTEMPTS_KEPT,
    ),
  }));
}

/** Starts a round in the latest attempt (starting an attempt first if there is none). */
export function startInterviewRound(
  state: ProgressState,
  id: string,
  roundIndex: number,
  now: Date,
): ProgressState {
  const interview = state.interviews.find((candidate) => candidate.id === id);
  if (!interview || roundIndex < 0 || roundIndex >= interview.rounds.length) return state;
  const started = interview.attempts.length > 0 ? state : startInterviewAttempt(state, id, now);
  return withInterview(started, id, (current) => {
    const attempt = current.attempts.at(-1)!;
    if (attempt.rounds[String(roundIndex)]) return current;
    const attempts = [...current.attempts];
    attempts[attempts.length - 1] = {
      ...attempt,
      rounds: { ...attempt.rounds, [roundIndex]: { startedAt: now.toISOString(), hints: {}, answers: {} } },
    };
    return { ...current, attempts };
  });
}

export function showInterviewHint(
  state: ProgressState,
  id: string,
  roundIndex: number,
  questionKey: string,
  totalHints: number,
): ProgressState {
  return withLatestRound(state, id, roundIndex, (round) => {
    if (round.finishedAt || round.answers[questionKey]) return round;
    const shown = Math.min((round.hints[questionKey] ?? 0) + 1, totalHints);
    return { ...round, hints: { ...round.hints, [questionKey]: shown } };
  });
}

export interface InterviewAnswerInput {
  /** raw score, 0..1 */
  score: number;
  selfAssessed: boolean;
  /** rubric points not covered */
  missed?: number[];
  response?: string;
}

/** Records the first answer to a question in the latest attempt; hints shown reduce its credit. */
export function recordInterviewAnswer(
  state: ProgressState,
  id: string,
  roundIndex: number,
  questionKey: string,
  input: InterviewAnswerInput,
  now: Date,
): ProgressState {
  return withLatestRound(state, id, roundIndex, (round) => {
    if (round.finishedAt || round.answers[questionKey]) return round;
    const hintsUsed = round.hints[questionKey] ?? 0;
    const score = Math.min(1, Math.max(0, input.score));
    const response = input.response?.slice(0, MAX_INTERVIEW_RESPONSE_CHARS);
    const answer: InterviewAnswer = {
      score,
      credit: creditFor(score, hintsUsed),
      hintsUsed,
      selfAssessed: input.selfAssessed,
      missed: input.missed ?? [],
      at: now.toISOString(),
      ...(response === undefined ? {} : { response }),
    };
    return { ...round, answers: { ...round.answers, [questionKey]: answer } };
  });
}

/** Ends a round; questions left unanswered score zero. */
export function finishInterviewRound(
  state: ProgressState,
  id: string,
  roundIndex: number,
  now: Date,
): ProgressState {
  return withLatestRound(state, id, roundIndex, (round) =>
    round.finishedAt ? round : { ...round, finishedAt: now.toISOString() },
  );
}
