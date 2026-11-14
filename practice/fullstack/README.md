# Full stack practice project

TypeScript exercises for Track I (full stack web development): plain TypeScript, React components
(tested with Testing Library in jsdom), Express APIs (tested with supertest, no port needed) and SQL
against a real PostgreSQL engine compiled to WebAssembly (PGlite - nothing to install).

- `exercises/<topic>/` - the files you change. They compile but are unsolved.
- `solutions/<topic>/` - reference solutions, at the same paths. Look only after trying.
- `tests/<topic>/*.test.ts(x)` - the tests that check your work. Every test file is an exercise; its tests
  sit in a `describe(name, { tags: ['@exercise'] }, ...)` block.

```bash
npm ci
npx vitest run tests/js/<name>.test.ts   # one exercise; read the first failure
npm run test:solutions                   # every test against the reference solutions
npm run verify                           # what CI runs: solutions pass, unsolved exercises fail
```

Needs Node.js 24 (`.nvmrc` at the repository root).
