import { defineConfig } from 'vitest/config';

// Tests run in Node by default. A React test opts into a browser-like DOM with the comment
// `// @vitest-environment jsdom` on its first line. Every exercise's tests sit in a
// `describe(name, { tags: ['@exercise'] }, ...)` block, as in the other practice projects.
export default defineConfig({
  test: {
    globals: true,
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    testTimeout: 15_000,
    tags: [{ name: '@exercise', description: 'Checks a learner exercise (fails until it is solved).' }],
  },
});
