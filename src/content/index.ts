/**
 * The content the app ships with: every YAML file under content/, bundled at build time
 * (no network requests), validated once at start-up.
 */
import rawCurriculum from '../../content/curriculum.yaml';
import rawInterviewConfig from '../../content/interviews/interviews.yaml';
import { validateContent } from './validate';

const byFile = (modules: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(modules).map(([file, data]) => [file.replace(/^(\.\.\/)+/, ''), data]));

const rawLessons = byFile(
  import.meta.glob('../../content/lessons/**/*.yaml', { eager: true, import: 'default' }),
);
const rawInterviewQuestions = byFile(
  import.meta.glob('../../content/interviews/questions/*.yaml', { eager: true, import: 'default' }),
);

export const contentResult = validateContent(rawCurriculum, rawLessons, {
  config: rawInterviewConfig,
  questions: rawInterviewQuestions,
});
