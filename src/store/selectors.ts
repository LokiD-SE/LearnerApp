/**
 * Read-only views of progress joined with content: lesson status, concept mastery,
 * the review queue and weak areas. Pure functions, so they are unit-tested directly.
 */
import type { ContentIndex } from '../content/validate';
import type { Exercise, Lesson, RecallCard } from '../content/schema';
import { conceptMastery, type ConceptItem, type ConceptMastery, type Evidence } from '../domain/mastery';
import { interleave, isDue } from '../domain/srs';
import { exerciseOf, isLessonComplete, itemKey, type ProgressState, type ReviewEntry } from './state';

export type LessonStatus = 'planned' | 'not-started' | 'in-progress' | 'completed' | 'mastered';

export const LESSON_STATUS_LABEL: Record<LessonStatus, string> = {
  planned: 'Planned',
  'not-started': 'Not started',
  'in-progress': 'In progress',
  completed: 'Completed',
  mastered: 'Mastered',
};

export function conceptItems(lesson: Lesson, conceptId: string): ConceptItem[] {
  return [
    ...lesson.exercises
      .filter((exercise) => exercise.concept === conceptId)
      .map((exercise) => ({ key: itemKey(lesson.id, exercise.id), skill: exercise.skill })),
    ...lesson.recall
      .filter((card) => card.concept === conceptId)
      .map((card) => ({ key: itemKey(lesson.id, card.id), skill: 'recall' as const })),
  ];
}

export function evidenceFor(state: ProgressState, conceptId: string): Evidence[] {
  return state.attempts
    .filter((attempt) => attempt.concept === conceptId)
    .map((attempt) => ({
      key: itemKey(attempt.lessonId, attempt.itemId),
      skill: attempt.skill,
      credit: attempt.credit,
      selfAssessed: attempt.selfAssessed,
      mode: attempt.mode,
      at: attempt.at,
      firstTry: attempt.firstTry,
    }));
}

export function masteryOf(lesson: Lesson, conceptId: string, state: ProgressState): ConceptMastery {
  return conceptMastery(conceptItems(lesson, conceptId), evidenceFor(state, conceptId));
}

export function lessonStatus(index: ContentIndex, state: ProgressState, lessonId: string): LessonStatus {
  const lesson = index.lessons.get(lessonId);
  if (!lesson) return 'planned';
  const progress = state.lessons[lessonId];
  const attempted = lesson.exercises.some((e) => exerciseOf(state, itemKey(lesson.id, e.id)).attempts > 0);
  if (isLessonComplete(state, lesson)) {
    const allMastered = lesson.concepts.every((c) => masteryOf(lesson, c.id, state).level === 'mastered');
    return allMastered ? 'mastered' : 'completed';
  }
  if (progress?.readAt || progress?.lastVisitedAt || attempted) return 'in-progress';
  return 'not-started';
}

export interface LessonProgressSummary {
  status: LessonStatus;
  requiredAttempted: number;
  requiredTotal: number;
  read: boolean;
}

export function lessonProgress(
  index: ContentIndex,
  state: ProgressState,
  lessonId: string,
): LessonProgressSummary {
  const lesson = index.lessons.get(lessonId);
  const required = lesson?.exercises.filter((e) => e.required) ?? [];
  return {
    status: lessonStatus(index, state, lessonId),
    requiredAttempted: required.filter((e) => exerciseOf(state, itemKey(lessonId, e.id)).attempts > 0).length,
    requiredTotal: required.length,
    read: Boolean(state.lessons[lessonId]?.readAt),
  };
}

export type ReviewItem =
  | (ReviewEntry & { key: string; lesson: Lesson; kind: 'exercise'; exercise: Exercise })
  | (ReviewEntry & { key: string; lesson: Lesson; kind: 'recall'; card: RecallCard });

/** Scheduled items whose lesson and item still exist in the current content. */
export function scheduledItems(index: ContentIndex, state: ProgressState): ReviewItem[] {
  const items: ReviewItem[] = [];
  for (const [key, entry] of Object.entries(state.reviews)) {
    const lesson = index.lessons.get(entry.lessonId);
    if (!lesson) continue;
    if (entry.kind === 'exercise') {
      const exercise = lesson.exercises.find((e) => e.id === entry.itemId);
      if (exercise) items.push({ ...entry, key, lesson, kind: 'exercise', exercise });
    } else {
      const card = lesson.recall.find((c) => c.id === entry.itemId);
      if (card) items.push({ ...entry, key, lesson, kind: 'recall', card });
    }
  }
  return items;
}

/** Due items, interleaved across concepts so similar ideas have to be told apart. */
export function dueReviews(index: ContentIndex, state: ProgressState, now: Date): ReviewItem[] {
  return interleave(scheduledItems(index, state).filter((item) => isDue(item, now)));
}

export function nextDueDate(index: ContentIndex, state: ProgressState, now: Date): Date | undefined {
  const upcoming = scheduledItems(index, state)
    .filter((item) => !isDue(item, now))
    .map((item) => Date.parse(item.due))
    .sort((a, b) => a - b);
  return upcoming.length ? new Date(upcoming[0]!) : undefined;
}

export interface ConceptRow {
  conceptId: string;
  name: string;
  lesson: Lesson;
  mastery: ConceptMastery;
}

export function conceptRows(index: ContentIndex, state: ProgressState): ConceptRow[] {
  const rows: ConceptRow[] = [];
  for (const lesson of index.lessons.values()) {
    for (const concept of lesson.concepts) {
      rows.push({
        conceptId: concept.id,
        name: concept.name,
        lesson,
        mastery: masteryOf(lesson, concept.id, state),
      });
    }
  }
  return rows;
}

/** Concepts with evidence that is not yet strong, weakest first. */
export function weakConcepts(index: ContentIndex, state: ProgressState): ConceptRow[] {
  return conceptRows(index, state)
    .filter((row) => row.mastery.level === 'attempted' || row.mastery.level === 'practising')
    .sort((a, b) => a.mastery.score - b.mastery.score);
}
