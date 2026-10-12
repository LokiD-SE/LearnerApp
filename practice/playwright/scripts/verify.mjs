// Verifies the practice project, like practice/verify.sh does for the Maven projects:
//   1. the code as given type-checks;
//   2. every test passes against the reference solutions (scripts/with-solutions.mjs);
//   3. every exercise spec file (tests tagged @exercise) fails against the unsolved exercises -
//      otherwise its tests don't check the learner's work;
//   4. every other test passes against the unsolved exercises.
import { spawnSync } from 'node:child_process';

const npx = (args, options = {}) =>
  spawnSync('npx', args, { stdio: 'inherit', shell: process.platform === 'win32', ...options });

const step = (title) => console.log(`\n== playwright: ${title}`);
const fail = (message) => {
  console.error(`FAIL: ${message}`);
  process.exit(1);
};

step('the code as given type-checks');
if (npx(['tsc', '--noEmit']).status !== 0) fail('type errors');

step('reference solutions must pass every test');
if (spawnSync('node', ['scripts/with-solutions.mjs'], { stdio: 'inherit' }).status !== 0)
  fail('solutions fail');

step('unsolved exercises must fail every exercise spec file');
const json = npx(['playwright', 'test', '--grep', '@exercise', '--reporter=json'], {
  stdio: ['ignore', 'pipe', 'inherit'],
  maxBuffer: 64 * 1024 * 1024,
});
const report = JSON.parse(json.stdout.toString());
const byFile = new Map();
const walk = (suite) => {
  for (const spec of suite.specs ?? []) {
    const results = byFile.get(spec.file) ?? { failed: 0, total: 0 };
    for (const t of spec.tests) {
      results.total += 1;
      if (t.status === 'unexpected') results.failed += 1;
    }
    byFile.set(spec.file, results);
  }
  for (const child of suite.suites ?? []) walk(child);
};
for (const suite of report.suites) walk(suite);
if (byFile.size === 0) fail('no exercise tests found');
let ok = true;
for (const [file, { failed, total }] of [...byFile].sort()) {
  if (failed === 0) {
    console.error(`FAIL: ${file} passes against the unsolved exercise, so it does not check the work`);
    ok = false;
  } else console.log(`ok: ${file} fails against the unsolved exercise (${failed} of ${total} tests)`);
}
if (!ok) process.exit(1);

step('tests that are not exercises must pass against the unsolved exercises');
if (npx(['playwright', 'test', '--grep-invert', '@exercise']).status !== 0) fail('journey tests fail');
console.log('\nverify: ok');
