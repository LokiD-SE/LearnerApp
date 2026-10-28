import { contentResult } from '../../src/content';
import type { ContentIndex, LessonRef } from '../../src/content/validate';
import type { KeyValueStore } from '../../src/store/storage';

/** The real, bundled content - tests run against what learners see. */
export function realIndex(): ContentIndex {
  if (!contentResult.ok) throw new Error(`content invalid:\n${contentResult.errors.join('\n')}`);
  return contentResult.index;
}

/** The real index plus a planned lesson (no content file) - every real lesson is written now. */
export function withPlannedLesson(index: ContentIndex): { index: ContentIndex; planned: LessonRef } {
  const planned: LessonRef = {
    id: 'planned-mutation-testing',
    title: 'Mutation testing for test suites',
    level: 'advanced',
    summary: 'Planned lesson used by the tests.',
    planned: true,
    subjectId: 'frameworks',
    moduleId: 'framework-design',
    stageId: 'stage-6',
  };
  return { index: { ...index, refs: new Map([...index.refs, [planned.id, planned]]) }, planned };
}

export function memoryStore(
  initial: Record<string, string> = {},
): KeyValueStore & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key]! : null),
    setItem: (key, value) => {
      data[key] = String(value);
    },
  };
}

export const at = (iso: string) => new Date(iso);
export const days = (n: number) => n * 24 * 60 * 60 * 1000;
