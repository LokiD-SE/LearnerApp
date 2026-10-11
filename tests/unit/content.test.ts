import { describe, expect, it } from 'vitest';
import { contentResult } from '../../src/content';
import { validateContent } from '../../src/content/validate';

describe('the bundled content', () => {
  it('is valid', () => {
    if (!contentResult.ok) throw new Error(contentResult.errors.join('\n'));
    expect(contentResult.ok).toBe(true);
  });

  it('has a fully written representative lesson covering the lesson template', () => {
    if (!contentResult.ok) throw new Error('invalid');
    const lesson = contentResult.index.lessons.get('idempotency-keys')!;
    const kinds = new Set(lesson.sections.map((s) => s.kind));
    for (const kind of [
      'intuition',
      'what',
      'why',
      'internals',
      'when',
      'visual',
      'steps',
      'example',
      'code',
      'line-by-line',
      'tests',
      'mistakes',
      'tradeoffs',
      'summary',
    ]) {
      expect(kinds, `missing section kind ${kind}`).toContain(kind);
    }
    expect(new Set(lesson.exercises.map((e) => e.type))).toEqual(
      new Set(['mcq', 'order', 'debug', 'short', 'testdesign', 'interview']),
    );
    expect(lesson.recall.length).toBeGreaterThan(0);
    expect(lesson.exercises.every((e) => e.hints.length > 0 && e.solution.length > 0)).toBe(true);
  });

  it('lists every stage and track', () => {
    if (!contentResult.ok) throw new Error('invalid');
    expect(contentResult.index.curriculum.stages).toHaveLength(7);
    expect(contentResult.index.curriculum.subjects.map((s) => s.track)).toEqual(
      expect.arrayContaining(['Track A', 'Track B', 'Track C', 'Track D', 'Track E', 'Track F', 'Track G']),
    );
  });
});

/* ------------------------------------------------------------------ content quality */

describe('every published lesson', () => {
  if (!contentResult.ok) throw new Error('invalid content');
  const published = [...contentResult.index.lessons.values()].filter((l) => l.status === 'published');

  it('exists in useful numbers', () => {
    expect(published.length).toBeGreaterThanOrEqual(8);
  });

  for (const lesson of published) {
    describe(lesson.id, () => {
      const kinds = new Set(lesson.sections.map((s) => s.kind));
      it('states its environment, sources and assumptions', () => {
        expect(lesson.environment?.length ?? 0).toBeGreaterThan(40);
      });
      it('covers the core of the lesson template', () => {
        for (const kind of ['intuition', 'what', 'why', 'mistakes', 'summary'] as const) {
          expect(kinds, `missing '${kind}' section`).toContain(kind);
        }
      });
      it('has at least one diagram', () => {
        expect(lesson.sections.some((s) => s.body.includes('```mermaid'))).toBe(true);
      });
      it('has varied practice with hints and worked solutions', () => {
        expect(lesson.exercises.length).toBeGreaterThanOrEqual(5);
        expect(lesson.exercises.some((e) => ['mcq', 'order', 'debug'].includes(e.type))).toBe(true);
        expect(lesson.exercises.some((e) => ['short', 'testdesign', 'interview'].includes(e.type))).toBe(
          true,
        );
        for (const exercise of lesson.exercises) {
          expect(exercise.hints.length, `${exercise.id} has no hints`).toBeGreaterThan(0);
        }
      });
      it('gives every wrong multiple-choice option its own explanation', () => {
        for (const exercise of lesson.exercises) {
          if (exercise.type !== 'mcq') continue;
          const feedback = exercise.options.map((o) => o.feedback);
          expect(new Set(feedback).size, `${exercise.id} reuses feedback text`).toBe(feedback.length);
        }
      });
      it('has enough recall cards for spaced review', () => {
        expect(lesson.recall.length).toBeGreaterThanOrEqual(4);
      });
      it('never contains anything that looks like a real card number', () => {
        const text = JSON.stringify(lesson);
        expect(text).not.toMatch(/\b(?:\d[ -]?){13,19}\b/);
      });
    });
  }
});

/* ------------------------------------------------------------------ validator */

const curriculum = (lessons: object[] = [{ id: 'l1' }]) => ({
  stages: [{ id: 's1', number: 1, title: 'S', summary: 'S' }],
  subjects: [
    {
      id: 'sub',
      track: 'T',
      title: 'Sub',
      summary: 'S',
      modules: [{ id: 'mod', title: 'M', stage: 's1', summary: 'M', lessons }],
    },
  ],
});

const lesson = (patch: Record<string, unknown> = {}) => ({
  id: 'l1',
  title: 'Lesson',
  subject: 'sub',
  module: 'mod',
  level: 'beginner',
  status: 'published',
  estimatedMinutes: 10,
  summary: 'S',
  concepts: [{ id: 'c1', name: 'C', summary: 'S' }],
  objectives: ['O'],
  sections: [{ id: 'what', kind: 'what', title: 'What', body: 'Body' }],
  exercises: [
    {
      id: 'e1',
      type: 'mcq',
      concept: 'c1',
      skill: 'application',
      title: 'Q',
      prompt: 'P',
      solution: 'S',
      options: [
        { id: 'a', text: 'A', feedback: 'F' },
        { id: 'b', text: 'B', feedback: 'F' },
      ],
      correct: ['a'],
    },
  ],
  ...patch,
});

const errorsOf = (cur: unknown, lessons: Record<string, unknown>) => {
  const result = validateContent(cur, lessons);
  return result.ok ? [] : result.errors;
};

describe('validateContent', () => {
  it('accepts a minimal valid set', () => {
    expect(errorsOf(curriculum(), { 'content/lessons/sub/l1.yaml': lesson() })).toEqual([]);
  });

  it('reports schema errors with the file and field', () => {
    const errors = errorsOf(curriculum(), { 'content/lessons/sub/l1.yaml': lesson({ level: 'guru' }) });
    expect(errors[0]).toMatch(/^content\/lessons\/sub\/l1\.yaml: level/);
  });

  it('requires the file name to match the lesson id', () => {
    expect(errorsOf(curriculum(), { 'content/lessons/sub/other.yaml': lesson() }).join()).toMatch(
      /file name must be l1\.yaml/,
    );
  });

  it('catches unknown prerequisites, next lessons and concepts', () => {
    const errors = errorsOf(curriculum(), {
      'content/lessons/sub/l1.yaml': lesson({
        prerequisites: ['nope'],
        next: ['missing'],
        recall: [{ id: 'r1', concept: 'ghost', prompt: 'P', answer: 'A' }],
      }),
    }).join('\n');
    expect(errors).toMatch(/unknown prerequisite 'nope'/);
    expect(errors).toMatch(/unknown next lesson 'missing'/);
    expect(errors).toMatch(/unknown concept 'ghost'/);
  });

  it('catches answers that are not options and debug lines past the end', () => {
    const errors = errorsOf(curriculum(), {
      'content/lessons/sub/l1.yaml': lesson({
        exercises: [
          { ...lesson().exercises[0], correct: ['z'] },
          {
            id: 'd1',
            type: 'debug',
            concept: 'c1',
            skill: 'analysis',
            title: 'D',
            prompt: 'P',
            solution: 'S',
            language: 'java',
            code: 'a\nb\n',
            correctLines: [3],
          },
        ],
      }),
    }).join('\n');
    expect(errors).toMatch(/correct answer 'z' is not an option/);
    expect(errors).toMatch(/line 3 is past the end of the code \(2 lines\)/);
  });

  it('requires a practical exercise for every concept of a published lesson', () => {
    const recognitionOnly = { ...lesson().exercises[0], skill: 'recognition' };
    expect(
      errorsOf(curriculum(), {
        'content/lessons/sub/l1.yaml': lesson({ exercises: [recognitionOnly] }),
      }).join(),
    ).toMatch(/concept 'c1' has no application or analysis exercise/);
  });

  it('needs a title and level for planned lessons, and rejects lessons outside the curriculum', () => {
    expect(
      errorsOf(curriculum([{ id: 'l1' }, { id: 'planned' }]), {
        'content/lessons/sub/l1.yaml': lesson(),
      }).join(),
    ).toMatch(/lesson 'planned' .* needs a title and level/);
    expect(
      errorsOf(curriculum([{ id: 'x', title: 'X', level: 'beginner' }]), {
        'content/lessons/sub/l1.yaml': lesson(),
      }).join(),
    ).toMatch(/lesson 'l1': not listed in any curriculum module/);
  });

  it('detects prerequisite cycles', () => {
    const errors = errorsOf(curriculum([{ id: 'l1' }, { id: 'l2' }]), {
      'content/lessons/sub/l1.yaml': lesson({ prerequisites: ['l2'] }),
      'content/lessons/sub/l2.yaml': lesson({
        id: 'l2',
        prerequisites: ['l1'],
        concepts: [{ id: 'c2', name: 'C', summary: 'S' }],
        exercises: [{ ...lesson().exercises[0], concept: 'c2' }],
      }),
    }).join('\n');
    expect(errors).toMatch(/prerequisite cycle/);
  });

  it('rejects duplicate ids and unknown fields', () => {
    const dup = lesson({ sections: [lesson().sections[0], lesson().sections[0]] });
    expect(errorsOf(curriculum(), { 'content/lessons/sub/l1.yaml': dup }).join()).toMatch(
      /duplicate id 'what'/,
    );
    expect(errorsOf(curriculum(), { 'content/lessons/sub/l1.yaml': lesson({ typo: 1 }) }).join()).toMatch(
      /typo|Unrecognized/,
    );
  });
});
