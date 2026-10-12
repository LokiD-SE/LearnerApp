import { describe, expect, it } from 'vitest';
import { isRubricExercise } from '../../src/content/schema';
import {
  attemptSummaries,
  bandOf,
  courseKey,
  courseOf,
  generateInterview,
  interviewCourses,
  nextRound,
  parseCourseKey,
  resolveQuestion,
  roundReport,
  roundResult,
  seededRandom,
  type CourseRef,
  type GeneratedInterview,
} from '../../src/store/interviews';
import {
  MAX_INTERVIEW_ATTEMPTS_KEPT,
  MAX_INTERVIEWS_KEPT,
  ProgressStateSchema,
  addInterview,
  deleteInterview,
  emptyState,
  finishInterviewRound,
  recordInterviewAnswer,
  showInterviewHint,
  startInterviewAttempt,
  startInterviewRound,
  type MockInterview,
  type ProgressState,
} from '../../src/store/state';
import { parseProgress } from '../../src/store/storage';
import { href, parseHash } from '../../src/ui/router';
import { at, realIndex } from './helpers';

const index = realIndex();
const content = index.interviews!;
const now = at('2026-10-12T09:00:00.000Z');
const later = (minutes: number) => new Date(now.getTime() + minutes * 60000);

const paymentsPath: CourseRef = { kind: 'path', id: 'payments-qa-core' };
const playwrightPath: CourseRef = { kind: 'path', id: 'playwright-engineer' };

const asStored = (generated: GeneratedInterview, id = `iv-${generated.seed}`): MockInterview => ({
  ...generated,
  id,
  createdAt: now.toISOString(),
  attempts: [],
});

const generate = (course: CourseRef, profileId: string, seed: number, previous: MockInterview[] = []) =>
  asStored(generateInterview(index, { course, profileId, seed, previous })!);

const allKeys = (interview: MockInterview) => interview.rounds.flatMap((round) => round.questions);

/* ------------------------------------------------------------------ content */

describe('interview content', () => {
  it('is loaded with every company category the learner asked for', () => {
    expect(content.profiles.map((p) => p.id)).toEqual([
      'google',
      'meta',
      'big4',
      'it-services',
      'mid-market',
      'startup',
    ]);
    for (const profile of content.profiles) {
      expect(profile.sources.length, `${profile.id} has no sources`).toBeGreaterThan(0);
    }
  });

  it('gives every bank question hints and a worked solution, and rubric questions a model answer', () => {
    for (const { exercise } of content.questions.values()) {
      expect(exercise.hints.length, `${exercise.id} has no hints`).toBeGreaterThan(0);
      expect(exercise.solution.length).toBeGreaterThan(0);
      if (isRubricExercise(exercise)) expect(exercise.rubric.length).toBeGreaterThanOrEqual(3);
      if (exercise.type === 'mcq') {
        const feedback = exercise.options.map((o) => o.feedback);
        expect(new Set(feedback).size, `${exercise.id} reuses feedback text`).toBe(feedback.length);
      }
    }
  });

  it('never contains anything that looks like a real card number', () => {
    expect(JSON.stringify([...content.questions.values()])).not.toMatch(/\b(?:\d[ -]?){13,19}\b/);
  });

  it('can fill every round of every company for every course', () => {
    for (const course of interviewCourses(index)) {
      for (const profile of content.profiles) {
        const interview = generate(course.ref, profile.id, 7);
        for (const round of interview.rounds) {
          const type = content.roundTypes.get(round.type)!;
          expect(round.questions, `${course.key} ${profile.id} ${round.type}`).toHaveLength(type.questions);
        }
      }
    }
  });
});

/* ------------------------------------------------------------------ courses */

describe('interview courses', () => {
  it('lists learning paths first, then tracks with published lessons', () => {
    const courses = interviewCourses(index);
    const kinds = courses.map((c) => c.ref.kind);
    expect(kinds.indexOf('subject')).toBeGreaterThan(kinds.lastIndexOf('path'));
    expect(courses.every((c) => c.lessons.length > 0)).toBe(true);
    expect(courses.map((c) => c.key)).toContain('path:playwright-engineer');
  });

  it('round-trips course keys', () => {
    expect(parseCourseKey(courseKey(playwrightPath))).toEqual(playwrightPath);
    expect(parseCourseKey('nonsense')).toBeUndefined();
  });
});

/* ------------------------------------------------------------------ generating */

describe('generateInterview', () => {
  it('is reproducible from its seed', () => {
    expect(generate(paymentsPath, 'any', 42)).toEqual(generate(paymentsPath, 'any', 42));
    expect(seededRandom(1)()).toBe(seededRandom(1)());
  });

  it("follows the company's reported loop in order", () => {
    for (const profile of content.profiles) {
      for (const seed of [1, 2, 3, 4, 5]) {
        const interview = generate(paymentsPath, profile.id, seed);
        expect(interview.profileId).toBe(profile.id);
        let stage = 0;
        for (const round of interview.rounds) {
          while (profile.stages[stage] && profile.stages[stage]!.label !== round.label) stage += 1;
          const match = profile.stages[stage];
          expect(match, `${profile.id}: '${round.label}' out of order`).toBeDefined();
          expect(match!.rounds).toContain(round.type);
          stage += 1;
        }
        // Stages without a chance always appear.
        const required = profile.stages.filter((s) => s.chance === undefined).map((s) => s.label);
        expect(interview.rounds.map((r) => r.label)).toEqual(expect.arrayContaining(required));
      }
    }
  });

  it('never repeats a question within an interview, and every question resolves', () => {
    for (const seed of [1, 2, 3, 4, 5, 6]) {
      const keys = allKeys(generate(playwrightPath, 'any', seed));
      expect(new Set(keys).size).toBe(keys.length);
      for (const key of keys) expect(resolveQuestion(index, key), key).toBeDefined();
    }
  });

  it("asks questions from the course's own lessons, and only from them", () => {
    const course = courseOf(index, playwrightPath)!;
    const lessonIds = new Set(course.lessons.map((l) => l.id));
    const keys = [1, 2, 3, 4].flatMap((seed) => allKeys(generate(playwrightPath, 'it-services', seed)));
    const fromLessons = keys.filter((key) => key.startsWith('lesson:'));
    expect(fromLessons.length).toBeGreaterThan(0);
    for (const key of fromLessons) expect(lessonIds.has(key.slice(7).split('/')[0]!)).toBe(true);
  });

  it('keeps subject-specific bank questions to courses with that subject', () => {
    const keys = new Set(
      [1, 2, 3, 4, 5, 6, 7, 8].flatMap((seed) => allKeys(generate(paymentsPath, 'big4', seed))),
    );
    const playwrightOnly = [...content.questions.values()]
      .filter((q) => q.subjects && !q.subjects.some((s) => courseOf(index, paymentsPath)!.subjects.has(s)))
      .map((q) => `bank:${q.exercise.id}`);
    expect(playwrightOnly.length).toBeGreaterThan(0);
    for (const key of playwrightOnly) expect(keys.has(key), key).toBe(false);
  });

  it("doesn't give a Playwright course the Selenium questions of a track it borrows one lesson from", () => {
    expect([...courseOf(index, playwrightPath)!.subjects]).toEqual(['playwright']);
    const keys = new Set(
      [1, 2, 3, 4, 5, 6, 7, 8].flatMap((seed) => allKeys(generate(playwrightPath, 'it-services', seed))),
    );
    for (const id of ['dd-mixing-waits', 'db-selenium-sleep', 'oa-java-string-equality']) {
      expect(keys.has(`bank:${id}`), id).toBe(false);
    }
  });

  it('with "any" company, picks a different company from the last interview for the course', () => {
    let previous: MockInterview[] = [];
    for (let seed = 1; seed <= 12; seed += 1) {
      const next = generate(paymentsPath, 'any', seed, previous);
      if (previous.length > 0) expect(next.profileId).not.toBe(previous.at(-1)!.profileId);
      previous = [...previous, next];
    }
  });

  it('gives a new interview for the same course and company a different set of rounds', () => {
    for (const profileId of ['google', 'meta', 'big4', 'startup']) {
      const first = generate(paymentsPath, profileId, 100);
      for (let seed = 101; seed <= 110; seed += 1) {
        const next = generate(paymentsPath, profileId, seed, [first]);
        expect(next.rounds.map((r) => r.type).join(), `${profileId} seed ${seed}`).not.toBe(
          first.rounds.map((r) => r.type).join(),
        );
      }
    }
  });

  it('asks questions not seen before first', () => {
    // Coding rounds draw only on the question bank, so the pool size is known.
    const pool = [...content.questions.values()].filter((q) => q.rounds.includes('coding-dsa')).length;
    const coding = (interview: MockInterview) =>
      interview.rounds.filter((r) => r.type === 'coding-dsa').flatMap((r) => r.questions);
    for (const seed of [1, 2, 3, 4, 5]) {
      const first = generate(paymentsPath, 'google', seed);
      const second = generate(paymentsPath, 'google', seed + 50, [first]);
      const repeated = coding(second).filter((key) => coding(first).includes(key)).length;
      expect(repeated).toBeLessThanOrEqual(Math.max(0, coding(first).length + coding(second).length - pool));
    }
  });
});

/* ------------------------------------------------------------------ taking an interview */

/** A Google interview for the payments path, stored in a fresh state. */
function stateWithInterview(seed = 3): { state: ProgressState; interview: MockInterview } {
  const interview = generate(paymentsPath, 'google', seed);
  return { state: addInterview(emptyState(), interview), interview };
}

const stored = (state: ProgressState, id: string) => state.interviews.find((i) => i.id === id)!;

/** Answers every question of a round with the same score, then finishes it. */
function takeRound(state: ProgressState, id: string, round: number, score: number, when: Date) {
  let next = startInterviewRound(state, id, round, when);
  for (const key of stored(next, id).rounds[round]!.questions) {
    next = recordInterviewAnswer(next, id, round, key, { score, selfAssessed: false }, when);
  }
  return finishInterviewRound(next, id, round, later(10));
}

describe('interview progress', () => {
  it('starts an attempt with the first round, and never restarts a started round', () => {
    const { state, interview } = stateWithInterview();
    const started = startInterviewRound(state, interview.id, 0, now);
    expect(stored(started, interview.id).attempts).toHaveLength(1);
    const again = startInterviewRound(started, interview.id, 0, later(5));
    expect(stored(again, interview.id).attempts[0]!.rounds['0']!.startedAt).toBe(now.toISOString());
  });

  it('counts only the first answer, charges for hints, and freezes a finished round', () => {
    const { state, interview } = stateWithInterview();
    const key = interview.rounds[0]!.questions[0]!;
    let next = startInterviewRound(state, interview.id, 0, now);
    next = showInterviewHint(next, interview.id, 0, key, 3);
    next = showInterviewHint(next, interview.id, 0, key, 3);
    next = recordInterviewAnswer(
      next,
      interview.id,
      0,
      key,
      { score: 1, selfAssessed: true, missed: [] },
      now,
    );
    next = recordInterviewAnswer(next, interview.id, 0, key, { score: 0, selfAssessed: true }, now);
    const answer = stored(next, interview.id).attempts[0]!.rounds['0']!.answers[key]!;
    expect(answer).toMatchObject({ score: 1, credit: 0.7, hintsUsed: 2 });

    next = finishInterviewRound(next, interview.id, 0, later(20));
    const other = interview.rounds[0]!.questions[1] ?? key;
    const after = recordInterviewAnswer(next, interview.id, 0, other, { score: 1, selfAssessed: false }, now);
    expect(after).toEqual(next);
  });

  it('is practice, not mastery evidence: lesson attempts and reviews are untouched', () => {
    const { state, interview } = stateWithInterview();
    const next = takeRound(state, interview.id, 0, 1, now);
    expect(next.attempts).toEqual([]);
    expect(next.reviews).toEqual({});
    expect(next.lessons).toEqual({});
  });

  it('keeps a bounded number of interviews and attempts, and deletes on request', () => {
    let state = emptyState();
    for (let i = 0; i < MAX_INTERVIEWS_KEPT + 3; i += 1) {
      state = addInterview(
        state,
        asStored(
          generateInterview(index, { course: paymentsPath, profileId: 'startup', seed: i, previous: [] })!,
          `iv-${i}`,
        ),
      );
    }
    expect(state.interviews).toHaveLength(MAX_INTERVIEWS_KEPT);
    expect(state.interviews[0]!.id).toBe('iv-3');
    for (let i = 0; i < MAX_INTERVIEW_ATTEMPTS_KEPT + 2; i += 1)
      state = startInterviewAttempt(state, 'iv-3', now);
    expect(stored(state, 'iv-3').attempts).toHaveLength(MAX_INTERVIEW_ATTEMPTS_KEPT);
    expect(deleteInterview(state, 'iv-3').interviews.some((i) => i.id === 'iv-3')).toBe(false);
  });

  it('loads progress saved before interviews existed, and round-trips an interview', () => {
    const older: Record<string, unknown> = { ...emptyState() };
    delete older.interviews;
    const parsed = parseProgress(JSON.stringify(older));
    expect(parsed.ok && parsed.state.interviews).toEqual([]);

    const { state, interview } = stateWithInterview();
    const taken = takeRound(state, interview.id, 0, 0.5, now);
    expect(ProgressStateSchema.parse(JSON.parse(JSON.stringify(taken)))).toEqual(taken);
  });
});

/* ------------------------------------------------------------------ scoring and feedback */

describe('interview scoring and feedback', () => {
  it('bands scores the way the report explains them', () => {
    expect(bandOf(0.85).id).toBe('strong');
    expect(bandOf(0.849).id).toBe('good');
    expect(bandOf(0.7).id).toBe('good');
    expect(bandOf(0.5).id).toBe('borderline');
    expect(bandOf(0.49).id).toBe('needs-work');
  });

  it('scores unanswered questions as zero', () => {
    const { state, interview } = stateWithInterview();
    const keys = interview.rounds[0]!.questions;
    let next = startInterviewRound(state, interview.id, 0, now);
    next = recordInterviewAnswer(next, interview.id, 0, keys[0]!, { score: 1, selfAssessed: false }, now);
    next = finishInterviewRound(next, interview.id, 0, later(30));
    const result = roundResult(
      index,
      stored(next, interview.id),
      stored(next, interview.id).attempts[0]!,
      0,
    )!;
    expect(result).toMatchObject({ answered: 1, total: keys.length, finished: true, minutes: 30 });
    expect(result.score).toBeCloseTo(1 / keys.length, 3);
  });

  it('reports strengths, areas to improve with missed rubric points, and progress across attempts', () => {
    const { state, interview } = stateWithInterview();
    // A round with a self-assessed (rubric) question.
    const r = interview.rounds.findIndex((round) =>
      round.questions.some((key) => isRubricExercise(resolveQuestion(index, key)!.exercise)),
    );
    const keys = interview.rounds[r]!.questions;
    const rubricKey = keys.find((key) => isRubricExercise(resolveQuestion(index, key)!.exercise))!;
    const rubric = (resolveQuestion(index, rubricKey)!.exercise as { rubric: string[] }).rubric;

    // Attempt 1: everything weak.
    let next = takeRound(state, interview.id, r, 0.25, now);
    // Attempt 2: the rubric question misses its first point; the others are perfect.
    next = startInterviewAttempt(next, interview.id, later(60));
    next = startInterviewRound(next, interview.id, r, later(60));
    for (const key of keys) {
      const input =
        key === rubricKey
          ? { score: (rubric.length - 1) / rubric.length, selfAssessed: true, missed: [0] }
          : { score: 1, selfAssessed: false };
      next = recordInterviewAnswer(next, interview.id, r, key, input, later(61));
    }
    next = finishInterviewRound(next, interview.id, r, later(90));

    const report = roundReport(index, stored(next, interview.id), 1, r)!;
    expect(report.history.map((h) => h.attempt)).toEqual([1, 2]);
    expect(report.previous).toBe(0.25);
    expect(report.best).toBe(0.25);
    expect(report.result.score).toBeGreaterThan(0.25);
    // Rubrics have at most six points, so missing one stays below the 85% "strong" line.
    expect(report.strengths).toHaveLength(keys.length - 1);
    const weak = report.improvements.find((o) => o.question.key === rubricKey)!;
    expect(weak.missedPoints).toEqual([rubric[0]]);
    expect(report.focusAreas.map((a) => a.name)).toContain(weak.question.focus.name);

    const first = roundReport(index, stored(next, interview.id), 0, r)!;
    expect(first.improvements).toHaveLength(keys.length);
    expect(first.previous).toBeUndefined();
  });

  it('summarises attempts and knows which round comes next', () => {
    const { state, interview } = stateWithInterview();
    expect(nextRound(interview)).toBe(0);
    let next = takeRound(state, interview.id, 0, 1, now);
    next = takeRound(next, interview.id, 1, 0.5, now);
    const current = stored(next, interview.id);
    expect(nextRound(current)).toBe(2);
    const [summary] = attemptSummaries(index, current);
    expect(summary!.overall).toBeCloseTo(0.75, 3);
    expect(summary!.complete).toBe(interview.rounds.length === 2);

    let all = next;
    for (let r = 2; r < interview.rounds.length; r += 1) all = takeRound(all, interview.id, r, 1, now);
    expect(nextRound(stored(all, interview.id))).toBeUndefined();
    expect(attemptSummaries(index, stored(all, interview.id))[0]!.complete).toBe(true);
  });

  it('points lesson questions back to the section that teaches them', () => {
    const lesson = courseOf(index, paymentsPath)!.lessons[0]!;
    const exercise = lesson.exercises[0]!;
    const question = resolveQuestion(index, `lesson:${lesson.id}/${exercise.id}`)!;
    expect(question.lesson?.id).toBe(lesson.id);
    expect(question.focus.href).toMatch(new RegExp(`^#/lesson/${lesson.id}(\\?focus=section-.+)?$`));
    expect(resolveQuestion(index, 'lesson:nope/nothing')).toBeUndefined();
    expect(resolveQuestion(index, 'bank:nothing')).toBeUndefined();
  });
});

describe('interview routes', () => {
  it('parse and round-trip', () => {
    expect(parseHash('#/interview')).toEqual({ name: 'interviews' });
    expect(parseHash(href.interviews('path:payments-qa-core'))).toEqual({
      name: 'interviews',
      course: 'path:payments-qa-core',
    });
    expect(parseHash(href.interview('iv-1'))).toEqual({ name: 'interview', id: 'iv-1' });
    expect(parseHash(href.interviewRound('iv-1', 2))).toEqual({
      name: 'interview-round',
      id: 'iv-1',
      round: 2,
    });
    expect(parseHash('#/interview/iv-1/round/0')).toEqual({
      name: 'not-found',
      path: '/interview/iv-1/round/0',
    });
  });
});
