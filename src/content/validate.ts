/**
 * Validates the whole content set: each file against its schema, then every internal
 * reference (prerequisites, modules, concepts, paths, next lessons) against the others.
 *
 * Used by the Vite plugin (a broken file fails `npm run dev` / `npm run build`), by the
 * content test, and at runtime to build the index the UI reads.
 */
import { CurriculumSchema, LessonSchema, isRubricExercise } from './schema.ts';
import type { Curriculum, CurriculumModule, CurriculumSubject, Lesson, Level } from './schema.ts';

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
}

export type ValidationResult = { ok: true; index: ContentIndex } | { ok: false; errors: string[] };

const formatZod = (file: string, issues: { path: PropertyKey[]; message: string }[]) =>
  issues.map((issue) => `${file}: ${issue.path.map(String).join('.') || '(root)'} - ${issue.message}`);

export function validateContent(
  rawCurriculum: unknown,
  rawLessons: Record<string, unknown>,
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
      if (exercise.type === 'mcq') {
        const optionIds = new Set(exercise.options.map((o) => o.id));
        if (optionIds.size !== exercise.options.length) errors.push(`${where}: duplicate option ids`);
        for (const id of exercise.correct) {
          if (!optionIds.has(id)) errors.push(`${where}: correct answer '${id}' is not an option`);
        }
        if (exercise.correct.length === exercise.options.length)
          errors.push(`${where}: every option is correct`);
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
      if (isRubricExercise(exercise) && new Set(exercise.rubric).size !== exercise.rubric.length) {
        errors.push(`${where}: duplicate rubric items`);
      }
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

  if (errors.length) return { ok: false, errors };
  return { ok: true, index: { curriculum, lessons, refs, subjects, modules, conceptLesson } };
}
