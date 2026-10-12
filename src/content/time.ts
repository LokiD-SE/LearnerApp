/**
 * Time estimates at every level of the curriculum: the parts of a lesson (objectives, each
 * section, practice, recall), a lesson, a chapter (module), a course (subject or learning path)
 * and a stage.
 *
 * A lesson's `estimatedMinutes` is the authored figure. The parts of a lesson share it by how
 * much each one asks of the learner (prose, code, diagrams, exercises), so the parts always add
 * up to the lesson; everything above a lesson is the sum of its lessons. Planned lessons have no
 * figure yet, so totals count them apart, with an "about" estimate from the published lessons.
 */
import type { Exercise, Lesson } from './schema';
import type { ContentIndex, LessonRef } from './validate';

/** Reading speed for technical prose, in words per minute. */
const WORDS_PER_MINUTE = 180;
/** Code is read line by line, more slowly than prose. */
const CODE_LINES_PER_MINUTE = 12;
const MINUTES_PER_DIAGRAM = 1.5;
const MINUTES_PER_RECALL_CARD = 1;
/** Typical time to attempt each kind of exercise, including reading its feedback. */
const EXERCISE_MINUTES: Record<Exercise['type'], number> = {
  mcq: 2,
  order: 3,
  debug: 4,
  short: 5,
  interview: 6,
  testdesign: 8,
  coding: 15,
};

export interface LessonTimes {
  /** The authored figure; the parts below add up to it. */
  total: number;
  objectives: number;
  /** section id -> minutes */
  sections: Map<string, number>;
  /** 0 when the lesson has no exercises */
  practice: number;
  /** 0 when the lesson has no recall cards */
  recall: number;
}

const words = (text: string) => text.split(/\s+/).filter(Boolean).length;

/** Reading effort of a Markdown body in minutes: prose, code blocks and Mermaid diagrams. */
export function readingWeight(markdown: string): number {
  let minutes = 0;
  // Odd-numbered pieces are the insides of ``` fences.
  markdown.split(/^```/m).forEach((piece, i) => {
    if (i % 2 === 0) {
      minutes += words(piece) / WORDS_PER_MINUTE;
      return;
    }
    const [info = '', ...lines] = piece.split('\n');
    if (info.trim().startsWith('mermaid')) minutes += MINUTES_PER_DIAGRAM;
    else minutes += lines.filter((line) => line.trim()).length / CODE_LINES_PER_MINUTE;
  });
  return minutes;
}

/**
 * Shares `total` whole minutes between parts in proportion to their weights, giving each part
 * at least a minute when there are enough to go round (largest remainder, so the sum is exact).
 */
export function share(total: number, weights: number[]): number[] {
  if (weights.length === 0) return [];
  const floor = total >= weights.length ? 1 : 0;
  const rest = total - floor * weights.length;
  const sum = weights.reduce((a, b) => a + b, 0);
  const ideal = weights.map((w) => (sum > 0 ? (rest * w) / sum : rest / weights.length));
  const result = ideal.map((x) => floor + Math.floor(x));
  let left = total - result.reduce((a, b) => a + b, 0);
  const byRemainder = ideal
    .map((x, i) => ({ i, remainder: x - Math.floor(x) }))
    .sort((a, b) => b.remainder - a.remainder || a.i - b.i);
  for (const { i } of byRemainder) {
    if (left <= 0) break;
    result[i]! += 1;
    left -= 1;
  }
  return result;
}

const cache = new WeakMap<Lesson, LessonTimes>();

export function lessonTimes(lesson: Lesson): LessonTimes {
  const cached = cache.get(lesson);
  if (cached) return cached;
  const weights = [
    readingWeight(lesson.objectives.join('\n')),
    ...lesson.sections.map((section) => readingWeight(section.body)),
  ];
  const hasPractice = lesson.exercises.length > 0;
  const hasRecall = lesson.recall.length > 0;
  if (hasPractice) weights.push(lesson.exercises.reduce((sum, e) => sum + EXERCISE_MINUTES[e.type], 0));
  if (hasRecall) weights.push(lesson.recall.length * MINUTES_PER_RECALL_CARD);

  const minutes = share(lesson.estimatedMinutes, weights);
  const sectionMinutes = minutes.slice(1, 1 + lesson.sections.length);
  const times: LessonTimes = {
    total: lesson.estimatedMinutes,
    objectives: minutes[0]!,
    sections: new Map(lesson.sections.map((section, i) => [section.id, sectionMinutes[i]!])),
    practice: hasPractice ? minutes[1 + lesson.sections.length]! : 0,
    recall: hasRecall ? minutes.at(-1)! : 0,
  };
  cache.set(lesson, times);
  return times;
}

export interface TimeTotal {
  /** Minutes of the published lessons. */
  minutes: number;
  /** Published lessons counted in `minutes`. */
  lessons: number;
  /** Planned lessons: not in `minutes`. */
  planned: number;
  /** About how long the planned lessons will take, from the typical published lesson. */
  plannedMinutes: number;
}

/** The median published lesson, rounded to 5 minutes: the stand-in for a planned lesson. */
export function typicalLessonMinutes(index: ContentIndex): number {
  const all = [...index.lessons.values()].map((lesson) => lesson.estimatedMinutes).sort((a, b) => a - b);
  if (all.length === 0) return 0;
  const mid = Math.floor(all.length / 2);
  const median = all.length % 2 ? all[mid]! : (all[mid - 1]! + all[mid]!) / 2;
  return Math.max(5, Math.round(median / 5) * 5);
}

export function totalTime(index: ContentIndex, refs: Iterable<LessonRef>): TimeTotal {
  const total: TimeTotal = { minutes: 0, lessons: 0, planned: 0, plannedMinutes: 0 };
  for (const ref of refs) {
    const lesson = index.lessons.get(ref.id);
    if (lesson) {
      total.minutes += lesson.estimatedMinutes;
      total.lessons += 1;
    } else total.planned += 1;
  }
  total.plannedMinutes = total.planned * typicalLessonMinutes(index);
  return total;
}

const refsWhere = (index: ContentIndex, keep: (ref: LessonRef) => boolean) =>
  [...index.refs.values()].filter(keep);

export const subjectTime = (index: ContentIndex, subjectId: string) =>
  totalTime(
    index,
    refsWhere(index, (ref) => ref.subjectId === subjectId),
  );
export const moduleTime = (index: ContentIndex, moduleId: string) =>
  totalTime(
    index,
    refsWhere(index, (ref) => ref.moduleId === moduleId),
  );
export const stageTime = (index: ContentIndex, stageId: string) =>
  totalTime(
    index,
    refsWhere(index, (ref) => ref.stageId === stageId),
  );
export const pathTime = (index: ContentIndex, lessonIds: string[]) =>
  totalTime(
    index,
    lessonIds.flatMap((id) => index.refs.get(id) ?? []),
  );

/** "45 min", "1 h", "2 h 5 min". */
export function formatMinutes(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  if (m < 60) return `${m} min`;
  const hours = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

/** A rough figure, rounded so it does not look precise: "about 40 min", "about 3 h", "about 31 h". */
export function formatAbout(minutes: number): string {
  if (minutes < 60) return `about ${formatMinutes(Math.max(5, Math.round(minutes / 5) * 5))}`;
  if (minutes < 180) return `about ${formatMinutes(Math.round(minutes / 30) * 30)}`;
  return `about ${Math.round(minutes / 60)} h`;
}

/** ISO 8601 duration for <time datetime>. */
export const isoDuration = (minutes: number) => `PT${Math.max(0, Math.round(minutes))}M`;
