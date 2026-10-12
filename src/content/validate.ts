/**
 * Validates the whole content set: each file against its schema, then every internal
 * reference (prerequisites, modules, concepts, paths, next lessons) against the others.
 *
 * Used by the Vite plugin (a broken file fails `npm run dev` / `npm run build`), by the
 * content test, and at runtime to build the index the UI reads.
 */
import {
  CurriculumSchema,
  InterviewConfigSchema,
  InterviewQuestionFileSchema,
  LessonSchema,
  isRubricExercise,
} from './schema.ts';
import type {
  BankQuestion,
  Competency,
  Curriculum,
  CurriculumModule,
  CurriculumSubject,
  Exercise,
  InterviewProfile,
  Lesson,
  Level,
  PracticeProject,
  RoundType,
} from './schema.ts';

export interface LessonRef {
  id: string;
  title: string;
  level: Level;
  summary: string;
  /** Planned lessons are listed in the curriculum but have no content file yet. */
  planned: boolean;
  subjectId: string;
  moduleId: string;
  stageId: string;
}

export interface ContentIndex {
  curriculum: Curriculum;
  lessons: Map<string, Lesson>;
  /** Every lesson the curriculum lists, published or planned, in curriculum order. */
  refs: Map<string, LessonRef>;
  subjects: Map<string, CurriculumSubject>;
  modules: Map<string, CurriculumModule & { subjectId: string }>;
  /** concept id -> lesson id that teaches it */
  conceptLesson: Map<string, string>;
  /** practice projects that coding exercises run in, by id */
  practiceProjects: Map<string, PracticeProject>;
  /** interview practice content, when the content set includes it */
  interviews: InterviewContent | null;
}

export interface InterviewContent {
  asOf: string;
  note: string;
  competencies: Map<string, Competency>;
  roundTypes: Map<string, RoundType>;
  /** in content order */
  profiles: InterviewProfile[];
  /** question-bank questions by exercise id */
  questions: Map<string, BankQuestion>;
}

/** The raw interview files: content/interviews/interviews.yaml and content/interviews/questions/*.yaml */
export interface RawInterviews {
  config: unknown;
  questions: Record<string, unknown>;
}

export type ValidationResult = { ok: true; index: ContentIndex } | { ok: false; errors: string[] };

const formatZod = (file: string, issues: { path: PropertyKey[]; message: string }[]) =>
  issues.map((issue) => `${file}: ${issue.path.map(String).join('.') || '(root)'} - ${issue.message}`);

/** Checks that only need the exercise itself (and the practice projects). */
function checkExercise(
  exercise: Exercise,
  where: string,
  practiceProjects: Map<string, PracticeProject>,
  errors: string[],
) {
  if (exercise.type === 'mcq') {
    const optionIds = new Set(exercise.options.map((o) => o.id));
    if (optionIds.size !== exercise.options.length) errors.push(`${where}: duplicate option ids`);
    for (const id of exercise.correct) {
      if (!optionIds.has(id)) errors.push(`${where}: correct answer '${id}' is not an option`);
    }
    if (exercise.correct.length === exercise.options.length) errors.push(`${where}: every option is correct`);
  }
  if (exercise.type === 'order') {
    const itemIds = new Set(exercise.items.map((i) => i.id));
    if (itemIds.size !== exercise.items.length) errors.push(`${where}: duplicate item ids`);
  }
  if (exercise.type === 'debug') {
    const lineCount = exercise.code.replace(/\n$/, '').split('\n').length;
    for (const line of [...exercise.correctLines, ...exercise.lineNotes.map((n) => n.line)]) {
      if (line > lineCount)
        errors.push(`${where}: line ${line} is past the end of the code (${lineCount} lines)`);
    }
  }
  if (exercise.type === 'coding' && !practiceProjects.has(exercise.project)) {
    errors.push(`${where}: unknown practice project '${exercise.project}'`);
  }
  if (isRubricExercise(exercise) && new Set(exercise.rubric).size !== exercise.rubric.length) {
    errors.push(`${where}: duplicate rubric items`);
  }
}

export function validateContent(
  rawCurriculum: unknown,
  rawLessons: Record<string, unknown>,
  rawInterviews?: RawInterviews,
): ValidationResult {
  const errors: string[] = [];

  const curriculumResult = CurriculumSchema.safeParse(rawCurriculum);
  if (!curriculumResult.success) {
    return { ok: false, errors: formatZod('content/curriculum.yaml', curriculumResult.error.issues) };
  }
  const curriculum = curriculumResult.data;

  const lessons = new Map<string, Lesson>();
  for (const [file, raw] of Object.entries(rawLessons)) {
    const parsed = LessonSchema.safeParse(raw);
    if (!parsed.success) {
      errors.push(...formatZod(file, parsed.error.issues));
      continue;
    }
    const lesson = parsed.data;
    const expectedName = `${lesson.id}.yaml`;
    if (!file.endsWith(`/${expectedName}`))
      errors.push(`${file}: file name must be ${expectedName} (the lesson id)`);
    if (lessons.has(lesson.id)) errors.push(`${file}: duplicate lesson id '${lesson.id}'`);
    lessons.set(lesson.id, lesson);
  }

  const practiceProjects = new Map<string, PracticeProject>();
  for (const project of curriculum.practice?.projects ?? []) {
    if (practiceProjects.has(project.id))
      errors.push(`curriculum: duplicate practice project id '${project.id}'`);
    practiceProjects.set(project.id, project);
  }

  const stageIds = new Set(curriculum.stages.map((s) => s.id));
  const subjects = new Map<string, CurriculumSubject>();
  const modules = new Map<string, CurriculumModule & { subjectId: string }>();
  const refs = new Map<string, LessonRef>();

  for (const subject of curriculum.subjects) {
    if (subjects.has(subject.id)) errors.push(`curriculum: duplicate subject id '${subject.id}'`);
    subjects.set(subject.id, subject);
    for (const mod of subject.modules) {
      if (modules.has(mod.id)) errors.push(`curriculum: duplicate module id '${mod.id}'`);
      if (!stageIds.has(mod.stage))
        errors.push(`curriculum: module '${mod.id}' names unknown stage '${mod.stage}'`);
      modules.set(mod.id, { ...mod, subjectId: subject.id });
      for (const entry of mod.lessons) {
        if (refs.has(entry.id)) {
          errors.push(`curriculum: lesson '${entry.id}' is listed in more than one module`);
          continue;
        }
        const lesson = lessons.get(entry.id);
        if (lesson) {
          if (lesson.subject !== subject.id || lesson.module !== mod.id) {
            errors.push(
              `lesson '${lesson.id}': subject/module '${lesson.subject}/${lesson.module}' does not match its curriculum place '${subject.id}/${mod.id}'`,
            );
          }
          refs.set(entry.id, {
            id: lesson.id,
            title: lesson.title,
            level: lesson.level,
            summary: lesson.summary,
            planned: false,
            subjectId: subject.id,
            moduleId: mod.id,
            stageId: mod.stage,
          });
        } else if (entry.title && entry.level) {
          refs.set(entry.id, {
            id: entry.id,
            title: entry.title,
            level: entry.level,
            summary: entry.summary ?? '',
            planned: true,
            subjectId: subject.id,
            moduleId: mod.id,
            stageId: mod.stage,
          });
        } else {
          errors.push(
            `curriculum: lesson '${entry.id}' in module '${mod.id}' has no content file, so it needs a title and level (planned lesson)`,
          );
        }
      }
    }
  }

  const conceptLesson = new Map<string, string>();
  for (const lesson of lessons.values()) {
    if (!refs.has(lesson.id)) errors.push(`lesson '${lesson.id}': not listed in any curriculum module`);

    const concepts = new Set<string>();
    for (const concept of lesson.concepts) {
      const owner = conceptLesson.get(concept.id);
      if (owner)
        errors.push(`lesson '${lesson.id}': concept '${concept.id}' is already taught by '${owner}'`);
      conceptLesson.set(concept.id, lesson.id);
      concepts.add(concept.id);
    }

    for (const prerequisite of lesson.prerequisites) {
      if (prerequisite === lesson.id) errors.push(`lesson '${lesson.id}': cannot be its own prerequisite`);
      else if (!refs.has(prerequisite))
        errors.push(`lesson '${lesson.id}': unknown prerequisite '${prerequisite}'`);
    }
    for (const next of lesson.next) {
      if (!refs.has(next)) errors.push(`lesson '${lesson.id}': unknown next lesson '${next}'`);
    }

    const ids = new Set<string>();
    const unique = (kind: string, id: string) => {
      if (ids.has(id)) errors.push(`lesson '${lesson.id}': duplicate id '${id}' (${kind})`);
      ids.add(id);
    };
    for (const section of lesson.sections) {
      unique('section', section.id);
      for (const concept of section.concepts) {
        if (!concepts.has(concept))
          errors.push(`lesson '${lesson.id}' section '${section.id}': unknown concept '${concept}'`);
      }
    }

    const checked = [
      ...lesson.exercises.map((exercise) => ({ exercise, kind: 'exercise' })),
      ...lesson.placement.map((exercise) => ({ exercise, kind: 'placement question' })),
    ];
    for (const { exercise, kind } of checked) {
      unique(kind, exercise.id);
      const where = `lesson '${lesson.id}' ${kind} '${exercise.id}'`;
      if (!concepts.has(exercise.concept)) errors.push(`${where}: unknown concept '${exercise.concept}'`);
      checkExercise(exercise, where, practiceProjects, errors);
    }
    for (const card of lesson.recall) {
      unique('recall card', card.id);
      if (!concepts.has(card.concept))
        errors.push(`lesson '${lesson.id}' recall '${card.id}': unknown concept '${card.concept}'`);
    }

    // Mastery needs practical evidence, so a published concept must be practised, not only recognised.
    if (lesson.status === 'published') {
      for (const concept of concepts) {
        const practical = lesson.exercises.some(
          (e) => e.concept === concept && (e.skill === 'application' || e.skill === 'analysis'),
        );
        if (!practical) {
          errors.push(`lesson '${lesson.id}': concept '${concept}' has no application or analysis exercise`);
        }
      }
    }
  }

  for (const path of curriculum.paths) {
    for (const id of path.lessons) {
      if (!refs.has(id)) errors.push(`curriculum: path '${path.id}' names unknown lesson '${id}'`);
    }
  }

  // Prerequisite cycles would make "what should I learn first" unanswerable.
  const visiting = new Set<string>();
  const done = new Set<string>();
  const visit = (id: string, trail: string[]) => {
    if (done.has(id)) return;
    if (visiting.has(id)) {
      errors.push(`prerequisite cycle: ${[...trail, id].join(' -> ')}`);
      return;
    }
    visiting.add(id);
    for (const prerequisite of lessons.get(id)?.prerequisites ?? []) visit(prerequisite, [...trail, id]);
    visiting.delete(id);
    done.add(id);
  };
  for (const id of lessons.keys()) visit(id, []);

  const interviews = rawInterviews
    ? validateInterviews(rawInterviews, { lessons, subjects, practiceProjects }, errors)
    : null;

  if (errors.length) return { ok: false, errors };
  return {
    ok: true,
    index: { curriculum, lessons, refs, subjects, modules, conceptLesson, practiceProjects, interviews },
  };
}

const LESSON_LINK = /#\/lesson\/([a-z0-9-]+)/g;

function validateInterviews(
  raw: RawInterviews,
  known: {
    lessons: Map<string, Lesson>;
    subjects: Map<string, CurriculumSubject>;
    practiceProjects: Map<string, PracticeProject>;
  },
  errors: string[],
): InterviewContent | null {
  const configFile = 'content/interviews/interviews.yaml';
  const parsed = InterviewConfigSchema.safeParse(raw.config);
  if (!parsed.success) {
    errors.push(...formatZod(configFile, parsed.error.issues));
    return null;
  }
  const config = parsed.data;
  const where = (id: string) => `${configFile} '${id}'`;
  // Links to lessons in interview text must keep working when lessons are renamed.
  const checkLinks = (place: string, value: unknown) => {
    for (const [, id] of JSON.stringify(value).matchAll(LESSON_LINK)) {
      if (!known.lessons.has(id!)) errors.push(`${place}: links to unknown lesson '${id}'`);
    }
  };

  const competencies = new Map<string, Competency>();
  for (const competency of config.competencies) {
    if (competencies.has(competency.id)) errors.push(`${where(competency.id)}: duplicate competency id`);
    competencies.set(competency.id, competency);
    if (competency.lesson && !known.lessons.has(competency.lesson))
      errors.push(`${where(competency.id)}: unknown lesson '${competency.lesson}'`);
    checkLinks(where(competency.id), competency.improve);
  }

  const roundTypes = new Map<string, RoundType>();
  for (const round of config.roundTypes) {
    if (roundTypes.has(round.id)) errors.push(`${where(round.id)}: duplicate round type id`);
    roundTypes.set(round.id, round);
    for (const subject of round.fromLessons?.subjects ?? []) {
      if (!known.subjects.has(subject)) errors.push(`${where(round.id)}: unknown subject '${subject}'`);
    }
  }

  const profileIds = new Set<string>();
  const usedRounds = new Set<string>();
  for (const profile of config.profiles) {
    if (profileIds.has(profile.id)) errors.push(`${where(profile.id)}: duplicate profile id`);
    profileIds.add(profile.id);
    for (const stage of profile.stages) {
      for (const round of stage.rounds) {
        usedRounds.add(round);
        if (!roundTypes.has(round))
          errors.push(`${where(profile.id)} stage '${stage.label}': unknown round type '${round}'`);
      }
    }
  }

  const questions = new Map<string, BankQuestion>();
  for (const [file, data] of Object.entries(raw.questions)) {
    const parsedFile = InterviewQuestionFileSchema.safeParse(data);
    if (!parsedFile.success) {
      errors.push(...formatZod(file, parsedFile.error.issues));
      continue;
    }
    for (const question of parsedFile.data.questions) {
      const { exercise } = question;
      const place = `${file} '${exercise.id}'`;
      if (questions.has(exercise.id)) errors.push(`${place}: duplicate question id`);
      questions.set(exercise.id, question);
      if (!competencies.has(exercise.concept))
        errors.push(`${place}: concept '${exercise.concept}' is not a competency`);
      for (const round of question.rounds) {
        if (!roundTypes.has(round)) errors.push(`${place}: unknown round type '${round}'`);
      }
      for (const subject of question.subjects ?? []) {
        if (!known.subjects.has(subject)) errors.push(`${place}: unknown subject '${subject}'`);
      }
      checkExercise(exercise, place, known.practiceProjects, errors);
      checkLinks(place, exercise);
    }
  }

  // Every round must be fillable for any course, even one whose lessons add nothing to it.
  for (const id of usedRounds) {
    const round = roundTypes.get(id);
    if (!round) continue;
    const forAnyCourse = [...questions.values()].filter((q) => q.rounds.includes(id) && !q.subjects).length;
    if (forAnyCourse < round.questions)
      errors.push(
        `${where(id)}: needs at least ${round.questions} question-bank questions open to any course, has ${forAnyCourse}`,
      );
  }

  return {
    asOf: config.asOf,
    note: config.note,
    competencies,
    roundTypes,
    profiles: config.profiles,
    questions,
  };
}
