// Verifies the practice project, like practice/verify.sh does for the Maven projects:
//   1. the code as given type-checks;
//   2. every test passes against the reference solutions (scripts/with-solutions.mjs);
//   3. every exercise test file (tests/**/*.test.ts[x]) fails against the unsolved exercises -
//      otherwise its tests don't check the learner's work.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';

const npx = (args, options = {}) =>
  spawnSync('npx', args, { stdio: 'inherit', shell: process.platform === 'win32', ...options });

const step = (title) => console.log(`\n== fullstack: ${title}`);
const fail = (message) => {
  console.error(`FAIL: ${message}`);
  process.exit(1);
};

step('the code as given type-checks');
if (npx(['tsc', '--noEmit']).status !== 0) fail('type errors');

step('reference solutions must pass every test');
if (spawnSync('node', ['scripts/with-solutions.mjs'], { stdio: 'inherit' }).status !== 0)
  fail('solutions fail');

step('unsolved exercises must fail every exercise test file');
// Vitest writes the JSON report to a file, not to standard output.
const reportDir = mkdtempSync(join(tmpdir(), 'learnerapp-fullstack-report-'));
const reportFile = join(reportDir, 'report.json');
npx(['vitest', 'run', '--reporter=json', `--outputFile=${reportFile}`], {
  stdio: ['ignore', 'ignore', 'inherit'],
});
const report = JSON.parse(readFileSync(reportFile, 'utf8'));
rmSync(reportDir, { recursive: true, force: true });
if (report.testResults.length === 0) fail('no exercise tests found');
let ok = true;
for (const file of [...report.testResults].sort((a, b) => a.name.localeCompare(b.name))) {
  const name = relative(process.cwd(), file.name);
  const total = file.assertionResults.length;
  const failed = file.assertionResults.filter((t) => t.status === 'failed').length;
  // A file that fails to load (an unsolved stub that throws on import) counts as failing.
  if (failed === 0 && file.status !== 'failed') {
    console.error(`FAIL: ${name} passes against the unsolved exercise, so it does not check the work`);
    ok = false;
  } else console.log(`ok: ${name} fails against the unsolved exercise (${failed} of ${total} tests)`);
}
if (!ok) process.exit(1);
console.log('\nverify: ok');
