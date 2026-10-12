/**
 * Content schema: the contract between the YAML files in content/ and the app.
 *
 * Educational content lives only in content/. The UI renders whatever these schemas
 * describe, so a new subject or lesson is a new YAML file, not new code.
 */
import { z } from 'zod';

export const LEVELS = ['beginner', 'intermediate', 'advanced', 'expert'] as const;
export type Level = (typeof LEVELS)[number];

/**
 * How much an exercise proves. Recognition (pick an option) proves least; applying the
 * concept to a new problem or analysing a failure proves most. See docs/MASTERY_MODEL.md.
 */
export const SKILLS = ['recognition', 'recall', 'application', 'analysis'] as const;
export type Skill = (typeof SKILLS)[number];

/** The mandatory lesson template (prompt section 6), one kind per template heading. */
export const SECTION_KINDS = [
  'intuition', // simple explanation and analogy
  'what',
  'why',
  'internals', // how it works internally
  'when', // when to use it and when not to
  'visual',
  'steps',
  'example', // real-world project example
  'code', // syntax, configuration, commands, code
  'line-by-line',
  'tests', // positive and negative test cases
  'mistakes', // common mistakes and debugging
  'tradeoffs', // limitations, trade-offs, alternatives
  'summary', // summary and quick reference
] as const;
export type SectionKind = (typeof SECTION_KINDS)[number];

export const Id = z
  .string()
  .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'ids are lower-case kebab-case (letters, digits, single hyphens)');
const Markdown = z.string().trim().min(1);
const Text = z.string().trim().min(1);
/** A path inside a practice project: relative, forward slashes, never leaving the folder. */
const RelativePath = z
  .string()
  .regex(/^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[\w./-]+$/, 'a relative path inside the project, without ..');

export const SectionSchema = z.strictObject({
  id: Id,
  kind: z.enum(SECTION_KINDS),
  title: Text,
  body: Markdown,
  /** Long worked examples can start collapsed so the lesson stays scannable. */
  collapsed: z.boolean().default(false),
  /** Concepts this section teaches - used to point a learner back here after a wrong answer. */
  concepts: z.array(Id).default([]),
});

const ExerciseBase = {
  id: Id,
  concept: Id,
  skill: z.enum(SKILLS),
  title: Text,
  prompt: Markdown,
  /** Progressive hints, shown one at a time, from a nudge to almost the answer. */
  hints: z.array(Markdown).default([]),
  /** Worked solution: the answer and the reasoning behind it. */
  solution: Markdown,
  /** A similar problem to try after the solution (transfer practice). */
  followUp: Markdown.optional(),
  /** Required exercises must be attempted before the lesson counts as completed. */
  required: z.boolean().default(true),
};

const Option = z.strictObject({
  id: Id,
  text: Markdown,
  /** Shown when this option is chosen: why it is right, or the misconception behind it. */
  feedback: Markdown,
});

export const McqSchema = z.strictObject({
  ...ExerciseBase,
  type: z.literal('mcq'),
  options: z.array(Option).min(2),
  correct: z.array(Id).min(1),
});

export const OrderSchema = z.strictObject({
  ...ExerciseBase,
  type: z.literal('order'),
  /** Listed in the correct order; the UI shuffles them. */
  items: z.array(z.strictObject({ id: Id, text: Markdown })).min(3),
});

export const DebugSchema = z.strictObject({
  ...ExerciseBase,
  type: z.literal('debug'),
  language: z.string().min(1),
  code: z.string().min(1),
  /** 1-based line numbers that, together, are the defect. */
  correctLines: z.array(z.number().int().positive()).min(1),
  /** Optional notes for lines a learner might wrongly pick. */
  lineNotes: z.array(z.strictObject({ line: z.number().int().positive(), note: Markdown })).default([]),
});

/** Free-text answers cannot be graded honestly by string matching, so the learner
 * compares their answer with a model answer and a rubric and records what they covered. */
const RubricFields = {
  modelAnswer: Markdown,
  rubric: z.array(Text).min(2),
};

export const ShortAnswerSchema = z.strictObject({
  ...ExerciseBase,
  ...RubricFields,
  type: z.literal('short'),
});
export const TestDesignSchema = z.strictObject({
  ...ExerciseBase,
  ...RubricFields,
  type: z.literal('testdesign'),
});
export const InterviewSchema = z.strictObject({
  ...ExerciseBase,
  ...RubricFields,
  type: z.literal('interview'),
  followUps: z.array(Markdown).default([]),
});

/**
 * Code the learner writes and runs on their own computer, in a practice project from the
 * repository (`practice:` in curriculum.yaml). The project's tests check the code; the app
 * cannot run them, so the learner self-assesses against the rubric, starting with "the tests pass".
 */
export const CodingSchema = z.strictObject({
  ...ExerciseBase,
  ...RubricFields,
  type: z.literal('coding'),
  /** Id of a practice project in curriculum.yaml. */
  project: Id,
  /** Files the learner changes, relative to the project folder. */
  files: z.array(RelativePath).min(1),
  /** The tests that check the work, relative to the project folder. */
  test: RelativePath,
  /** The command that runs those tests, from the project folder. */
  command: Text,
});

export const ExerciseSchema = z.discriminatedUnion('type', [
  McqSchema,
  OrderSchema,
  DebugSchema,
  ShortAnswerSchema,
  TestDesignSchema,
  InterviewSchema,
  CodingSchema,
]);

/**
 * Placement questions decide whether a learner can skip ("test out of") a lesson. They are
 * auto-graded only - a placement result must not rest on self-assessment - and separate from
 * the lesson's practice exercises so practice stays fresh for those who study the lesson.
 */
export const PlacementQuestionSchema = z.discriminatedUnion('type', [McqSchema, OrderSchema, DebugSchema]);

export const RecallCardSchema = z.strictObject({
  id: Id,
  concept: Id,
  prompt: Markdown,
  answer: Markdown,
});

export const ConceptSchema = z.strictObject({
  id: Id,
  name: Text,
  summary: Text,
});

export const LessonSchema = z.strictObject({
  id: Id,
  title: Text,
  subject: Id,
  module: Id,
  level: z.enum(LEVELS),
  status: z.enum(['published', 'draft']),
  estimatedMinutes: z.number().int().positive(),
  summary: Text,
  /** Versions, environment and assumptions the lesson depends on. */
  environment: Markdown.optional(),
  prerequisites: z.array(Id).default([]),
  concepts: z.array(ConceptSchema).min(1),
  objectives: z.array(Text).min(1),
  sections: z.array(SectionSchema).min(1),
  exercises: z.array(ExerciseSchema).default([]),
  placement: z.array(PlacementQuestionSchema).default([]),
  recall: z.array(RecallCardSchema).default([]),
  next: z.array(Id).default([]),
  tags: z.array(Text).default([]),
});

const LessonEntry = z.strictObject({
  id: Id,
  /** Planned lessons (no file yet) need these so the curriculum can show them. */
  title: Text.optional(),
  level: z.enum(LEVELS).optional(),
  summary: Text.optional(),
});

export const CurriculumSchema = z.strictObject({
  stages: z
    .array(z.strictObject({ id: Id, number: z.number().int().positive(), title: Text, summary: Text }))
    .min(1),
  subjects: z
    .array(
      z.strictObject({
        id: Id,
        track: Text,
        title: Text,
        summary: Text,
        modules: z
          .array(
            z.strictObject({ id: Id, title: Text, stage: Id, summary: Text, lessons: z.array(LessonEntry) }),
          )
          .min(1),
      }),
    )
    .min(1),
  paths: z
    .array(
      z.strictObject({
        id: Id,
        title: Text,
        level: z.enum(LEVELS),
        summary: Text,
        lessons: z.array(Id).min(1),
      }),
    )
    .default([]),
  /** Practice projects in the repository that coding exercises run in. */
  practice: z
    .strictObject({
      repository: z.url({ protocol: /^https$/ }),
      branch: Text,
      projects: z
        .array(
          z.strictObject({
            id: Id,
            title: Text,
            /** Folder in the repository, for example practice/java. */
            path: RelativePath,
            summary: Text,
            /** How to get and run the project the first time. */
            setup: Markdown,
          }),
        )
        .min(1),
    })
    .optional(),
});

/* ------------------------------------------------------------------ interview practice */

export const EXERCISE_TYPES = [
  'mcq',
  'order',
  'debug',
  'short',
  'testdesign',
  'interview',
  'coding',
] as const;

/** What interview feedback is given on; every question-bank question names one. */
export const CompetencySchema = z.strictObject({
  id: Id,
  name: Text,
  /** How to get better at it, shown as an area to improve. */
  improve: Markdown,
  /** A lesson that teaches it. */
  lesson: Id.optional(),
});

/** A kind of interview round (coding, behavioural...), with what it assesses and how to prepare. */
export const RoundTypeSchema = z.strictObject({
  id: Id,
  title: Text,
  /** The usual length of the real round. */
  minutes: z.number().int().positive(),
  /** How many questions a practice round asks. */
  questions: z.number().int().min(1).max(6),
  summary: Text,
  assesses: z.array(Text).min(1),
  tips: z.array(Text).min(1),
  /** Exercises from the chosen course's lessons that suit this round, besides the question bank. */
  fromLessons: z
    .strictObject({
      types: z.array(z.enum(EXERCISE_TYPES)).min(1),
      skills: z.array(z.enum(SKILLS)).optional(),
      subjects: z.array(Id).optional(),
    })
    .optional(),
});

/** A company's (or a kind of company's) reported interview loop, with its sources. */
export const InterviewProfileSchema = z.strictObject({
  id: Id,
  name: Text,
  category: Text,
  summary: Text,
  notes: z.array(Text).default([]),
  sources: z.array(z.strictObject({ title: Text, url: z.url({ protocol: /^https$/ }) })).min(1),
  /** The loop in order. A stage names one or more round types (one is chosen per interview);
   * `chance` makes a stage that only some candidates get appear in that share of interviews. */
  stages: z
    .array(
      z.strictObject({
        label: Text,
        rounds: z.array(Id).min(1),
        chance: z.number().gt(0).lt(1).optional(),
      }),
    )
    .min(2),
});

export const InterviewConfigSchema = z.strictObject({
  /** When the profiles were last checked against their sources (YYYY-MM-DD). */
  asOf: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'a date like 2026-10-12'),
  note: Markdown,
  competencies: z.array(CompetencySchema).min(1),
  roundTypes: z.array(RoundTypeSchema).min(1),
  profiles: z.array(InterviewProfileSchema).min(1),
});

/** A file of question-bank questions; each exercise's `concept` is a competency id. */
export const InterviewQuestionFileSchema = z.strictObject({
  questions: z
    .array(
      z.strictObject({
        /** Round types the question can be asked in. */
        rounds: z.array(Id).min(1),
        /** Only for courses that include one of these subjects; omitted means any course. */
        subjects: z.array(Id).min(1).optional(),
        exercise: ExerciseSchema,
      }),
    )
    .min(1),
});

export type Section = z.infer<typeof SectionSchema>;
export type Exercise = z.infer<typeof ExerciseSchema>;
export type McqExercise = z.infer<typeof McqSchema>;
export type OrderExercise = z.infer<typeof OrderSchema>;
export type DebugExercise = z.infer<typeof DebugSchema>;
export type CodingExercise = z.infer<typeof CodingSchema>;
export type RubricExercise =
  | z.infer<typeof ShortAnswerSchema>
  | z.infer<typeof TestDesignSchema>
  | z.infer<typeof InterviewSchema>
  | CodingExercise;
export type PlacementQuestion = z.infer<typeof PlacementQuestionSchema>;
export type RecallCard = z.infer<typeof RecallCardSchema>;
export type Concept = z.infer<typeof ConceptSchema>;
export type Lesson = z.infer<typeof LessonSchema>;
export type Curriculum = z.infer<typeof CurriculumSchema>;
export type CurriculumSubject = Curriculum['subjects'][number];
export type CurriculumModule = CurriculumSubject['modules'][number];
export type Stage = Curriculum['stages'][number];
export type LearningPath = Curriculum['paths'][number];
export type Practice = NonNullable<Curriculum['practice']>;
export type PracticeProject = Practice['projects'][number];
export type Competency = z.infer<typeof CompetencySchema>;
export type RoundType = z.infer<typeof RoundTypeSchema>;
export type InterviewProfile = z.infer<typeof InterviewProfileSchema>;
export type InterviewConfig = z.infer<typeof InterviewConfigSchema>;
export type BankQuestion = z.infer<typeof InterviewQuestionFileSchema>['questions'][number];

export const isRubricExercise = (exercise: Exercise): exercise is RubricExercise =>
  exercise.type === 'short' ||
  exercise.type === 'testdesign' ||
  exercise.type === 'interview' ||
  exercise.type === 'coding';
