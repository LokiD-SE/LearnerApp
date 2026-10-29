import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: [
      'dist',
      'coverage',
      'test-results',
      'playwright-report',
      'node_modules',
      'practice/**/target',
      'practice/**/node_modules',
      'practice/**/test-results',
      'practice/**/playwright-report',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
  {
    // the service worker template; vite.config.ts replaces __PRECACHE__ at build time
    files: ['src/pwa/service-worker.js'],
    languageOptions: { globals: { ...globals.serviceworker, __PRECACHE__: 'readonly' } },
  },
  {
    // unsolved exercise stubs keep the parameters the learner will need
    files: ['practice/**/exercises/**'],
    rules: { '@typescript-eslint/no-unused-vars': 'off' },
  },
);
