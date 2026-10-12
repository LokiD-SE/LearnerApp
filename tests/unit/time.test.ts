import { describe, expect, it } from 'vitest';
import {
  formatAbout,
  formatMinutes,
  lessonTimes,
  moduleTime,
  pathTime,
  readingWeight,
  share,
  stageTime,
  subjectTime,
  totalTime,
  typicalLessonMinutes,
} from '../../src/content/time';
import { minutesLeft } from '../../src/store/selectors';
import { emptyState } from '../../src/store/state';
import { realIndex } from './helpers';

const index = realIndex();
const published = [...index.lessons.values()];
const sum = (values: Iterable<number>) => [...values].reduce((a, b) => a + b, 0);

describe('share', () => {
  it('adds up to the total exactly and follows the weights', () => {
    const parts = share(50, [1, 2, 7]);
    expect(sum(parts)).toBe(50);
    expect(parts[2]).toBeGreaterThan(parts[1]!);
    expect(parts[1]).toBeGreaterThan(parts[0]!);
  });

  it('gives every part at least a minute when there are enough to go round', () => {
    const parts = share(10, [0, 0.01, 100]);
    expect(parts.every((m) => m >= 1)).toBe(true);
    expect(sum(parts)).toBe(10);
  });

  it('shares evenly when nothing has weight, and handles no parts', () => {
    expect(share(9, [0, 0, 0])).toEqual([3, 3, 3]);
    expect(share(5, [])).toEqual([]);
  });
});

describe('readingWeight', () => {
  it('counts prose, code lines and diagrams differently', () => {
    const prose = readingWeight(Array.from({ length: 180 }, () => 'word').join(' '));
    expect(prose).toBeCloseTo(1);
    const code = readingWeight('```java\n' + 'int a = 1;\n'.repeat(12) + '```\n');
    expect(code).toBeCloseTo(1);
    const diagram = readingWeight('```mermaid\nflowchart LR\n  A --> B\n```\n');
    expect(diagram).toBeCloseTo(1.5);
  });
});

describe('lessonTimes', () => {
  it('splits every published lesson into parts that add up to its estimate', () => {
    for (const lesson of published) {
      const times = lessonTimes(lesson);
      expect(times.total).toBe(lesson.estimatedMinutes);
      expect(times.sections.size).toBe(lesson.sections.length);
      const parts = times.objectives + sum(times.sections.values()) + times.practice + times.recall;
      expect(parts, lesson.id).toBe(lesson.estimatedMinutes);
      for (const minutes of times.sections.values()) expect(minutes, lesson.id).toBeGreaterThanOrEqual(1);
      expect(times.practice > 0).toBe(lesson.exercises.length > 0);
      expect(times.recall > 0).toBe(lesson.recall.length > 0);
    }
  });
});

describe('totals', () => {
  it('adds a course up from its chapters, and chapters from their lessons', () => {
    for (const subject of index.curriculum.subjects) {
      const course = subjectTime(index, subject.id);
      const chapters = subject.modules.map((mod) => moduleTime(index, mod.id));
      expect(course.minutes).toBe(sum(chapters.map((c) => c.minutes)));
      expect(course.lessons + course.planned).toBe(sum(subject.modules.map((m) => m.lessons.length)));
      for (const [i, mod] of subject.modules.entries()) {
        const minutes = sum(mod.lessons.map(({ id }) => index.lessons.get(id)?.estimatedMinutes ?? 0));
        expect(chapters[i]!.minutes).toBe(minutes);
      }
    }
  });

  it('keeps planned lessons out of the published time and estimates them apart', () => {
    const all = totalTime(index, index.refs.values());
    expect(all.minutes).toBe(sum(published.map((l) => l.estimatedMinutes)));
    expect(all.lessons).toBe(index.lessons.size);
    expect(all.planned).toBe(index.refs.size - index.lessons.size);
    expect(all.plannedMinutes).toBe(all.planned * typicalLessonMinutes(index));
    expect(typicalLessonMinutes(index) % 5).toBe(0);
    expect(sum(index.curriculum.stages.map((s) => stageTime(index, s.id).minutes))).toBe(all.minutes);
  });

  it('totals a learning path in its own order and counts what is left', () => {
    const path = index.curriculum.paths.find((p) => p.id === 'payments-qa-core')!;
    const time = pathTime(index, path.lessons);
    expect(time.lessons).toBe(path.lessons.length);
    const refs = path.lessons.map((id) => index.refs.get(id)!);
    expect(minutesLeft(index, emptyState(), refs)).toBe(time.minutes);
    const testedOut = {
      ...emptyState(),
      placements: {
        [path.lessons[0]!]: {
          result: 'tested-out' as const,
          at: '2026-10-01T09:00:00.000Z',
          correct: 2,
          total: 2,
          source: 'lesson' as const,
          answers: {},
        },
      },
    };
    const first = index.lessons.get(path.lessons[0]!)!;
    expect(minutesLeft(index, testedOut, refs)).toBe(time.minutes - first.estimatedMinutes);
  });
});

describe('formatting', () => {
  it('formats exact and rough times', () => {
    expect(formatMinutes(45)).toBe('45 min');
    expect(formatMinutes(60)).toBe('1 h');
    expect(formatMinutes(125)).toBe('2 h 5 min');
    expect(formatAbout(42)).toBe('about 40 min');
    expect(formatAbout(100)).toBe('about 1 h 30 min');
    expect(formatAbout(1890)).toBe('about 32 h');
  });
});
