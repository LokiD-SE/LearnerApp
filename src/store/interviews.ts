/**
 * Interview practice: generating a practice interview for a course from the reported company
 * loops, and scoring and explaining each round. Pure functions over the content index and the
 * stored interviews, so the rules are unit-testable; changes to progress go through state.ts.
 */
import type { BankQuestion, Exercise, InterviewProfile, Lesson, RoundType } from '../content/schema';
import { isRubricExercise } from '../content/schema';
import type { ContentIndex, InterviewContent } from '../content/validate';
import type { InterviewAnswer, InterviewAttempt, MockInterview } from './state';

/* ------------------------------------------------------------------ courses */

export interface CourseRef {
  kind: 'path' | 'subject';
  id: string;
}

export interface Course {
  ref: CourseRef;
  key: string;
  title: string;
  /** published lessons, in course order */
  lessons: Lesson[];
  /** the subjects the course is about: those at least two of its lessons belong to (or all, if none) */
  subjects: Set<string>;
}

export const courseKey = (ref: CourseRef) => `${ref.kind}:${ref.id}`;

export function parseCourseKey(key: string): CourseRef | undefined {
  const match = /^(path|subject):([a-z0-9-]+)$/.exec(key);
  return match ? { kind: match[1] as CourseRef['kind'], id: match[2]! } : undefined;
}

export function courseOf(index: ContentIndex, ref: CourseRef): Course | undefined {
  let ids: string[];
  let title: string;
  if (ref.kind === 'path') {
    const path = index.curriculum.paths.find((candidate) => candidate.id === ref.id);
    if (!path) return undefined;
    ids = path.lessons;
    title = path.title;
  } else {
    const subject = index.subjects.get(ref.id);
    if (!subject) return undefined;
    ids = subject.modules.flatMap((mod) => mod.lessons.map((entry) => entry.id));
    title = `${subject.track}: ${subject.title}`;
  }
  const lessons = ids
    .map((id) => index.lessons.get(id))
    .filter((lesson): lesson is Lesson => lesson?.status === 'published');
  // A path that borrows one lesson from another track (page objects, say) shouldn't get that
  // track's tool-specific questions.
  const counts = new Map<string, number>();
  for (const lesson of lessons) counts.set(lesson.subject, (counts.get(lesson.subject) ?? 0) + 1);
  const main = [...counts].filter(([, count]) => count >= 2).map(([subject]) => subject);
  return {
    ref,
    key: courseKey(ref),
    title,
    lessons,
    subjects: new Set(main.length > 0 ? main : counts.keys()),
  };
}

/** Learning paths, then tracks - those with at least one published lesson. */
export function interviewCourses(index: ContentIndex): Course[] {
  const refs: CourseRef[] = [
    ...index.curriculum.paths.map((path) => ({ kind: 'path' as const, id: path.id })),
    ...index.curriculum.subjects.map((subject) => ({ kind: 'subject' as const, id: subject.id })),
  ];
  return refs
    .map((ref) => courseOf(index, ref))
    .filter((course): course is Course => Boolean(course && course.lessons.length > 0));
}

/* ------------------------------------------------------------------ questions */

export const bankKey = (id: string) => `bank:${id}`;
export const lessonKey = (lessonId: string, exerciseId: string) => `lesson:${lessonId}/${exerciseId}`;

export interface Focus {
  /** the competency or lesson concept the question is about */
  name: string;
  /** how to improve (markdown) */
  improve?: string;
  /** where to learn it */
  href?: string;
}

export interface ResolvedQuestion {
  key: string;
  exercise: Exercise;
  /** the lesson a lesson exercise comes from; undefined for question-bank questions */
  lesson?: Lesson;
  focus: Focus;
}

const lessonHref = (lessonId: string, focus?: string) =>
  `#/lesson/${encodeURIComponent(lessonId)}${focus ? `?focus=${encodeURIComponent(focus)}` : ''}`;

/** A stored question key back to its content; undefined if the content no longer has it. */
export function resolveQuestion(index: ContentIndex, key: string): ResolvedQuestion | undefined {
  if (key.startsWith('bank:')) {
    const question = index.interviews?.questions.get(key.slice('bank:'.length));
    if (!question) return undefined;
    const competency = index.interviews?.competencies.get(question.exercise.concept);
    return {
      key,
      exercise: question.exercise,
      focus: {
        name: competency?.name ?? question.exercise.concept,
        ...(competency ? { improve: competency.improve } : {}),
        ...(competency?.lesson ? { href: lessonHref(competency.lesson) } : {}),
      },
    };
  }
  const match = /^lesson:([a-z0-9-]+)\/([a-z0-9-]+)$/.exec(key);
  const lesson = match ? index.lessons.get(match[1]!) : undefined;
  const exercise = lesson?.exercises.find((candidate) => candidate.id === match![2]);
  if (!lesson || !exercise) return undefined;
  const concept = lesson.concepts.find((candidate) => candidate.id === exercise.concept);
  const section = lesson.sections.find(
    (candidate) => candidate.kind !== 'summary' && candidate.concepts.includes(exercise.concept),
  );
  return {
    key,
    exercise,
    lesson,
    focus: {
      name: concept?.name ?? exercise.concept,
      ...(concept ? { improve: `${concept.summary} Re-read it in "${lesson.title}".` } : {}),
      href: lessonHref(lesson.id, section ? `section-${section.id}` : undefined),
    },
  };
}

/* ------------------------------------------------------------------ generating */

/** Small, fast, seedable random numbers (mulberry32), so an interview can be regenerated from its seed. */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function newSeed(): number {
  const values = new Uint32Array(1);
  globalThis.crypto.getRandomValues(values);
  return values[0]! >>> 1;
}

const pick = <T>(items: readonly T[], random: () => number): T => items[Math.floor(random() * items.length)]!;

export type GeneratedInterview = Pick<MockInterview, 'course' | 'profileId' | 'seed' | 'rounds'>;

export interface GenerateInput {
  course: CourseRef;
  /** a profile id, or 'any' for a different company each time */
  profileId: string;
  seed: number;
  /** interviews generated before, oldest first - used to vary companies, rounds and questions */
  previous: readonly MockInterview[];
}

interface Candidate {
  key: string;
  concept: string;
  fromLesson: boolean;
  /** how many earlier interviews asked it */
  seen: number;
  /** random sort key; lower comes first */
  order: number;
}

const MAX_REROLLS = 8;

/**
 * Builds an interview: the company's loop (optional stages included by their reported chance,
 * one round type per stage), then questions for each round from the question bank and from the
 * course's own lessons. Questions not asked before come first, concepts vary within a round,
 * and a new interview for the same course and company avoids repeating the last set of rounds.
 */
export function generateInterview(index: ContentIndex, input: GenerateInput): GeneratedInterview | undefined {
  const content = index.interviews;
  const course = courseOf(index, input.course);
  if (!content || !course) return undefined;
  const random = seededRandom(input.seed);
  const sameCourse = input.previous.filter((p) => courseKey(p.course) === course.key);

  const profile = chooseProfile(content.profiles, input.profileId, sameCourse.at(-1)?.profileId, random);
  if (!profile) return undefined;

  const lastRounds = sameCourse
    .filter((p) => p.profileId === profile.id)
    .at(-1)
    ?.rounds.map((round) => round.type)
    .join();
  let stages = chooseStages(profile, random);
  for (let reroll = 0; reroll < MAX_REROLLS && stages.map((s) => s.type).join() === lastRounds; reroll += 1) {
    stages = chooseStages(profile, random);
  }

  const seen = new Map<string, number>();
  for (const interview of input.previous) {
    for (const round of interview.rounds) {
      for (const key of round.questions) seen.set(key, (seen.get(key) ?? 0) + 1);
    }
  }

  const used = new Set<string>();
  const rounds: GeneratedInterview['rounds'] = [];
  for (const stage of stages) {
    const roundType = content.roundTypes.get(stage.type);
    if (!roundType) continue;
    const questions = chooseQuestions(content, roundType, course, seen, used, random);
    if (questions.length === 0) continue;
    for (const key of questions) used.add(key);
    rounds.push({ type: roundType.id, label: stage.label, questions });
  }
  return { course: course.ref, profileId: profile.id, seed: input.seed, rounds };
}

function chooseProfile(
  profiles: readonly InterviewProfile[],
  requested: string,
  last: string | undefined,
  random: () => number,
): InterviewProfile | undefined {
  if (requested !== 'any') return profiles.find((profile) => profile.id === requested);
  const fresh = profiles.filter((profile) => profile.id !== last);
  return profiles.length === 0 ? undefined : pick(fresh.length > 0 ? fresh : profiles, random);
}

function chooseStages(profile: InterviewProfile, random: () => number) {
  return profile.stages.flatMap((stage) => {
    // Draw both numbers every time so the sequence doesn't depend on earlier outcomes.
    const included = random();
    const type = pick(stage.rounds, random);
    return stage.chance !== undefined && included >= stage.chance ? [] : [{ label: stage.label, type }];
  });
}

const byFreshness = (a: Candidate, b: Candidate) => a.seen - b.seen || a.order - b.order;

function chooseQuestions(
  content: InterviewContent,
  roundType: RoundType,
  course: Course,
  seen: Map<string, number>,
  used: Set<string>,
  random: () => number,
): string[] {
  const candidate = (key: string, concept: string, fromLesson: boolean, boost = 0): Candidate => ({
    key,
    concept,
    fromLesson,
    seen: seen.get(key) ?? 0,
    order: random() - boost,
  });

  // Questions written for the course's subjects get a head start over general ones.
  const bank = [...content.questions.values()]
    .filter((q) => q.rounds.includes(roundType.id) && fitsCourse(q, course))
    .map((q) => candidate(bankKey(q.exercise.id), q.exercise.concept, false, q.subjects ? 0.5 : 0))
    .filter((c) => !used.has(c.key))
    .sort(byFreshness);

  const filter = roundType.fromLessons;
  const fromLessons = filter
    ? course.lessons
        .filter((lesson) => !filter.subjects || filter.subjects.includes(lesson.subject))
        .flatMap((lesson) =>
          lesson.exercises
            .filter(
              (e) => filter.types.includes(e.type) && (!filter.skills || filter.skills.includes(e.skill)),
            )
            .map((e) => candidate(lessonKey(lesson.id, e.id), `${lesson.id}/${e.concept}`, true)),
        )
        .filter((c) => !used.has(c.key))
        .sort(byFreshness)
    : [];

  // About half the questions come from the course's lessons when it has suitable exercises
  // (a one-question round: every other time).
  const wanted = roundType.questions;
  const share = wanted === 1 ? (random() < 0.5 ? 1 : 0) : Math.ceil(wanted / 2);
  const fromCourse = Math.min(fromLessons.length, share);
  const chosen: Candidate[] = [];
  const take = (pool: Candidate[], count: number) => {
    // First pass: a concept not yet in the round; second pass: anything left.
    for (const varied of [true, false]) {
      for (const c of pool) {
        if (count <= 0) return;
        if (chosen.includes(c) || (varied && chosen.some((other) => other.concept === c.concept))) continue;
        chosen.push(c);
        count -= 1;
      }
    }
  };
  take(fromLessons, fromCourse);
  take(bank, wanted - chosen.length);
  take(fromLessons, wanted - chosen.length);
  return chosen.map((c) => c.key);
}

const fitsCourse = (question: BankQuestion, course: Course) =>
  !question.subjects || question.subjects.some((subject) => course.subjects.has(subject));

/* ------------------------------------------------------------------ scoring and feedback */

export interface Band {
  id: 'strong' | 'good' | 'borderline' | 'needs-work';
  label: string;
  /** what a real interviewer's write-up would probably say */
  signal: string;
}

const BANDS: readonly (Band & { min: number })[] = [
  { min: 0.85, id: 'strong', label: 'Strong', signal: 'a strong hire signal' },
  { min: 0.7, id: 'good', label: 'Good', signal: 'a hire signal' },
  { min: 0.5, id: 'borderline', label: 'Borderline', signal: 'a mixed signal that could go either way' },
  { min: 0, id: 'needs-work', label: 'Needs work', signal: 'no hire signal yet' },
];

export function bandOf(score: number): Band {
  const { id, label, signal } = BANDS.find((band) => score >= band.min) ?? BANDS[BANDS.length - 1]!;
  return { id, label, signal };
}

/** A question counts as answered well from this credit on. */
export const STRONG_ANSWER = 0.85;

export interface QuestionOutcome {
  question: ResolvedQuestion;
  answer?: InterviewAnswer;
  /** 0 when unanswered */
  credit: number;
  /** rubric points the answer did not cover */
  missedPoints: string[];
}

export interface RoundResult {
  /** average credit over the round's questions; unanswered ones count as zero */
  score: number;
  band: Band;
  answered: number;
  total: number;
  finished: boolean;
  /** minutes between starting and finishing */
  minutes?: number;
}

export function roundOutcomes(
  index: ContentIndex,
  interview: MockInterview,
  attempt: InterviewAttempt,
  roundIndex: number,
): QuestionOutcome[] {
  const round = interview.rounds[roundIndex];
  const record = attempt.rounds[String(roundIndex)];
  if (!round) return [];
  return round.questions.flatMap((key) => {
    const question = resolveQuestion(index, key);
    if (!question) return [];
    const answer = record?.answers[key];
    const exercise = question.exercise;
    const missedPoints =
      answer && isRubricExercise(exercise)
        ? answer.missed.flatMap((i) => (exercise.rubric[i] === undefined ? [] : [exercise.rubric[i]!]))
        : [];
    return [{ question, credit: answer?.credit ?? 0, missedPoints, ...(answer ? { answer } : {}) }];
  });
}

/** The round's result in one attempt; undefined if that attempt hasn't started the round. */
export function roundResult(
  index: ContentIndex,
  interview: MockInterview,
  attempt: InterviewAttempt,
  roundIndex: number,
): RoundResult | undefined {
  const record = attempt.rounds[String(roundIndex)];
  if (!record) return undefined;
  const outcomes = roundOutcomes(index, interview, attempt, roundIndex);
  const score = outcomes.length === 0 ? 0 : outcomes.reduce((sum, o) => sum + o.credit, 0) / outcomes.length;
  const rounded = Math.round(score * 1000) / 1000;
  return {
    score: rounded,
    band: bandOf(rounded),
    answered: outcomes.filter((o) => o.answer).length,
    total: outcomes.length,
    finished: Boolean(record.finishedAt),
    ...(record.finishedAt
      ? { minutes: Math.max(0, (Date.parse(record.finishedAt) - Date.parse(record.startedAt)) / 60000) }
      : {}),
  };
}

export interface FocusArea extends Focus {
  /** titles of the questions that showed it */
  questions: string[];
}

export interface RoundReport {
  result: RoundResult;
  strengths: QuestionOutcome[];
  /** weakest first */
  improvements: QuestionOutcome[];
  focusAreas: FocusArea[];
  /** this round's finished results in every attempt up to this one, oldest first */
  history: { attempt: number; score: number }[];
  previous?: number;
  best?: number;
}

/** The end-of-round report: score, strengths, areas to improve, and progress on earlier attempts. */
export function roundReport(
  index: ContentIndex,
  interview: MockInterview,
  attemptIndex: number,
  roundIndex: number,
): RoundReport | undefined {
  const attempt = interview.attempts[attemptIndex];
  const result = attempt && roundResult(index, interview, attempt, roundIndex);
  if (!attempt || !result) return undefined;

  const outcomes = roundOutcomes(index, interview, attempt, roundIndex);
  const strengths = outcomes.filter((o) => o.credit >= STRONG_ANSWER);
  const improvements = outcomes.filter((o) => o.credit < STRONG_ANSWER).sort((a, b) => a.credit - b.credit);

  const focusAreas: FocusArea[] = [];
  for (const outcome of improvements) {
    const { focus, exercise } = outcome.question;
    const existing = focusAreas.find((area) => area.name === focus.name);
    if (existing) existing.questions.push(exercise.title);
    else focusAreas.push({ ...focus, questions: [exercise.title] });
  }

  const history = interview.attempts.slice(0, attemptIndex + 1).flatMap((earlier, i) => {
    const earlierResult = roundResult(index, interview, earlier, roundIndex);
    return earlierResult?.finished ? [{ attempt: i + 1, score: earlierResult.score }] : [];
  });
  const before = history.filter((entry) => entry.attempt < attemptIndex + 1);
  return {
    result,
    strengths,
    improvements,
    focusAreas,
    history,
    ...(before.length > 0
      ? { previous: before.at(-1)!.score, best: Math.max(...before.map((entry) => entry.score)) }
      : {}),
  };
}

export interface AttemptSummary {
  attempt: number;
  startedAt: string;
  /** per round; undefined where the attempt didn't start the round */
  rounds: (RoundResult | undefined)[];
  /** average of the finished rounds */
  overall?: number;
  complete: boolean;
}

export function attemptSummaries(index: ContentIndex, interview: MockInterview): AttemptSummary[] {
  return interview.attempts.map((attempt, i) => {
    const rounds = interview.rounds.map((_, r) => roundResult(index, interview, attempt, r));
    const finished = rounds.filter((round): round is RoundResult => Boolean(round?.finished));
    return {
      attempt: i + 1,
      startedAt: attempt.startedAt,
      rounds,
      ...(finished.length > 0
        ? {
            overall:
              Math.round((finished.reduce((sum, round) => sum + round.score, 0) / finished.length) * 1000) /
              1000,
          }
        : {}),
      complete: finished.length === interview.rounds.length,
    };
  });
}

/** The round to do next in the latest attempt: the first not finished, or undefined when all are. */
export function nextRound(interview: MockInterview): number | undefined {
  const attempt = interview.attempts.at(-1);
  if (!attempt) return 0;
  const index = interview.rounds.findIndex((_, r) => !attempt.rounds[String(r)]?.finishedAt);
  return index < 0 ? undefined : index;
}
