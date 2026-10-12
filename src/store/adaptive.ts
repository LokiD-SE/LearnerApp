/**
 * Adaptive practice: what to re-read after a wrong answer, and what to practise next.
 * Pure functions over content and progress, so the rules are unit-tested directly.
 * The rules are documented in docs/MASTERY_MODEL.md ("Adaptive practice").
 */
import type { Exercise, Lesson, Section } from '../content/schema';
import { isRubricExercise } from '../content/schema';
import type { ContentIndex } from '../content/validate';
import type { ConceptMastery } from '../domain/mastery';
import { masteryOf } from './selectors';
import { exerciseOf, itemKey, type ProgressState } from './state';

/** How many sections to suggest re-reading after a wrong answer. */
export const REMEDIATION_SECTIONS = 2;
/** Items answered more recently than this are left out of a practice session. */
export const RECENT_MS = 10 * 60 * 1000;
export const DEFAULT_SESSION_SIZE = 8;

const isPractical = (exercise: Exercise) => exercise.skill === 'application' || exercise.skill === 'analysis';

export interface Remediation {
  /** the most specific sections teaching the concept, in lesson order */
  sections: Section[];
  /** another exercise on the same concept to try next */
  sibling: Exercise | undefined;
}

/**
 * After a wrong answer: the sections that teach the concept most specifically (a section
 * about only this concept beats one covering three), and a sibling exercise on the same
 * concept - one not tried yet if possible, otherwise the one with the weakest last result.
 */
export function remediationFor(lesson: Lesson, exercise: Exercise, state: ProgressState): Remediation {
  const sections = lesson.sections
    .map((section, order) => ({ section, order }))
    .filter(({ section }) => section.concepts.includes(exercise.concept))
    .sort((a, b) => a.section.concepts.length - b.section.concepts.length || a.order - b.order)
    .slice(0, REMEDIATION_SECTIONS)
    .sort((a, b) => a.order - b.order)
    .map(({ section }) => section);

  const siblings = lesson.exercises.filter((e) => e.concept === exercise.concept && e.id !== exercise.id);
  const sibling = [...siblings].sort((a, b) => {
    const sa = exerciseOf(state, itemKey(lesson.id, a.id));
    const sb = exerciseOf(state, itemKey(lesson.id, b.id));
    if ((sa.attempts === 0) !== (sb.attempts === 0)) return sa.attempts === 0 ? -1 : 1;
    return (sa.lastCredit ?? 0) - (sb.lastCredit ?? 0);
  })[0];

  return { sections, sibling };
}

export interface PracticeItem {
  lesson: Lesson;
  exercise: Exercise;
  conceptId: string;
  conceptName: string;
  /** shown to the learner: why this item was chosen */
  reason: string;
  priority: number;
}

/** A lesson the learner has engaged with: opened, read, answered or tested out of. */
export function isEngaged(state: ProgressState, lesson: Lesson): boolean {
  const progress = state.lessons[lesson.id];
  return Boolean(
    progress?.readAt ||
    progress?.lastVisitedAt ||
    state.placements[lesson.id] ||
    lesson.exercises.some((e) => exerciseOf(state, itemKey(lesson.id, e.id)).attempts > 0),
  );
}

const percent = (value: number) => `${Math.round(value * 100)}%`;

/** How urgent practice on a concept is, and how to explain it. */
function conceptPriority(mastery: ConceptMastery): { priority: number; reason: string } {
  if (mastery.itemsAttempted === 0) return { priority: 0.6, reason: 'Not practised yet' };
  if (!mastery.practical) {
    return mastery.score >= 0.8
      ? { priority: 0.75, reason: 'You recognise this - now show you can apply it' }
      : {
          priority: 0.7 + (1 - mastery.score) * 0.3,
          reason: `Weak so far (${percent(mastery.score)}) - apply it to a new problem`,
        };
  }
  if (mastery.level === 'proficient')
    return { priority: 0.25, reason: 'Recall it again later to make it stick' };
  // Practical and scoring well: what's missing is coverage of the concept's other items.
  if (mastery.score >= 0.8) return { priority: 0.35, reason: 'Going well - now cover the rest of it' };
  return {
    priority: 0.4 + (1 - mastery.score) * 0.5,
    reason: `Still practising (${percent(mastery.score)})`,
  };
}

/**
 * Builds a practice session from the lessons the learner has engaged with (or one lesson).
 *
 * - Concepts are ranked by need: weak or recognition-only concepts first, untried concepts
 *   next, proficient ones last; mastered concepts are left out.
 * - Within a concept, practical (application/analysis) exercises come first when the
 *   concept has no practical success yet; then auto-graded before self-assessed, untried
 *   before tried, and weakest last result first.
 * - Items answered in the last RECENT_MS are skipped, so a session isn't a repeat of what
 *   was just done.
 * - Up to two items per urgent concept, one otherwise, taken round-robin across concepts
 *   so consecutive items come from different concepts (interleaving).
 */
export function buildPracticeSession(
  index: ContentIndex,
  state: ProgressState,
  now: Date,
  options: { lessonId?: string; size?: number } = {},
): PracticeItem[] {
  const size = options.size ?? DEFAULT_SESSION_SIZE;
  const lessons = options.lessonId
    ? [index.lessons.get(options.lessonId)].filter((l): l is Lesson => Boolean(l))
    : [...index.refs.values()]
        .map((ref) => index.lessons.get(ref.id))
        .filter((l): l is Lesson => Boolean(l) && isEngaged(state, l!));

  const groups: { priority: number; items: PracticeItem[] }[] = [];
  for (const lesson of lessons) {
    for (const concept of lesson.concepts) {
      const mastery = masteryOf(lesson, concept.id, state);
      if (mastery.level === 'mastered') continue;
      const { priority, reason } = conceptPriority(mastery);

      const fresh = lesson.exercises.filter((exercise) => {
        if (exercise.concept !== concept.id) return false;
        const lastAt = exerciseOf(state, itemKey(lesson.id, exercise.id)).lastAt;
        return !lastAt || now.getTime() - Date.parse(lastAt) >= RECENT_MS;
      });
      const ranked = [...fresh].sort((a, b) => {
        if (!mastery.practical && isPractical(a) !== isPractical(b)) return isPractical(a) ? -1 : 1;
        if (isRubricExercise(a) !== isRubricExercise(b)) return isRubricExercise(a) ? 1 : -1;
        const sa = exerciseOf(state, itemKey(lesson.id, a.id));
        const sb = exerciseOf(state, itemKey(lesson.id, b.id));
        if ((sa.attempts === 0) !== (sb.attempts === 0)) return sa.attempts === 0 ? -1 : 1;
        return (sa.lastCredit ?? 0) - (sb.lastCredit ?? 0);
      });
      const take = priority >= 0.7 ? 2 : 1;
      const items = ranked.slice(0, take).map((exercise) => ({
        lesson,
        exercise,
        conceptId: concept.id,
        conceptName: concept.name,
        reason,
        priority,
      }));
      if (items.length) groups.push({ priority, items });
    }
  }

  // Most urgent concepts first; a stable sort keeps curriculum order among equals.
  groups.sort((a, b) => b.priority - a.priority);
  const session: PracticeItem[] = [];
  for (let round = 0; session.length < size && groups.some((g) => g.items[round]); round += 1) {
    for (const group of groups) {
      const item = group.items[round];
      if (item && session.length < size) session.push(item);
    }
  }
  return session;
}
