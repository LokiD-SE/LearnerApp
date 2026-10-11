/**
 * The content the app ships with: every YAML file under content/, bundled at build time
 * (no network requests), validated once at start-up.
 */
import rawCurriculum from '../../content/curriculum.yaml';
import { validateContent } from './validate';

const rawLessons = Object.fromEntries(
  Object.entries(import.meta.glob('../../content/lessons/**/*.yaml', { eager: true, import: 'default' })).map(
    ([file, data]) => [file.replace(/^(\.\.\/)+/, ''), data],
  ),
);

export const contentResult = validateContent(rawCurriculum, rawLessons);
