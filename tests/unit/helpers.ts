import { contentResult } from '../../src/content';
import type { ContentIndex } from '../../src/content/validate';
import type { KeyValueStore } from '../../src/store/storage';

/** The real, bundled content - tests run against what learners see. */
export function realIndex(): ContentIndex {
  if (!contentResult.ok) throw new Error(`content invalid:\n${contentResult.errors.join('\n')}`);
  return contentResult.index;
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
