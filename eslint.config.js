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
    // unsolved exercise stubs keep the parameters the learner will need
    files: ['practice/**/exercises/**'],
    rules: { '@typescript-eslint/no-unused-vars': 'off' },
  },
);
