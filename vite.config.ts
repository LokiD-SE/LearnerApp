/// <reference types="vitest/config" />
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import preact from '@preact/preset-vite';
import { parse } from 'yaml';
import { validateContent } from './src/content/validate.ts';

const CONTENT_DIR = join(import.meta.dirname, 'content');

const yamlFiles = (dir: string): string[] =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? yamlFiles(join(dir, entry.name))
      : entry.name.endsWith('.yaml')
        ? [join(dir, entry.name)]
        : [],
  );

/** Loads content/*.yaml as JS modules and refuses to start or build on invalid content. */
function learnerContent(): Plugin {
  const checkAll = () => {
    const read = (file: string) => parse(readFileSync(file, 'utf8')) as unknown;
    const lessons = Object.fromEntries(
      yamlFiles(join(CONTENT_DIR, 'lessons')).map((file) => [
        relative(import.meta.dirname, file),
        read(file),
      ]),
    );
    const result = validateContent(read(join(CONTENT_DIR, 'curriculum.yaml')), lessons);
    if (!result.ok) throw new Error(`Invalid content:\n  ${result.errors.join('\n  ')}`);
  };
  return {
    name: 'learner-content',
    buildStart() {
      checkAll();
    },
    handleHotUpdate({ file }) {
      if (file.startsWith(CONTENT_DIR)) checkAll();
    },
    transform(code, id) {
      if (!id.endsWith('.yaml')) return null;
      try {
        return { code: `export default ${JSON.stringify(parse(code))};`, map: null };
      } catch (error) {
        throw new Error(`${relative(import.meta.dirname, id)}: ${(error as Error).message}`, {
          cause: error,
        });
      }
    },
  };
}

export default defineConfig({
  // Relative asset paths + hash routing: the build works from any folder or sub-path
  // (GitHub Pages project site, a static server, or `npm run preview`).
  base: './',
  plugins: [preact(), learnerContent()],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
