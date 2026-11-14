// Runs the tests against the reference solutions: copies the project to a temporary folder, puts
// solutions/ in place of exercises/, type-checks and runs Vitest there. Arguments go to Vitest.
// Usage: npm run test:solutions [-- vitest arguments]
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const work = mkdtempSync(join(tmpdir(), 'learnerapp-fullstack-solutions-'));
const skip = /^(node_modules|exercises)(\/|\\|$)/;
cpSync(root, work, { recursive: true, filter: (source) => !skip.test(relative(root, source)) });
cpSync(join(root, 'solutions'), join(work, 'exercises'), { recursive: true });
symlinkSync(
  join(root, 'node_modules'),
  join(work, 'node_modules'),
  process.platform === 'win32' ? 'junction' : 'dir',
);

const run = (args) =>
  spawnSync('npx', args, { cwd: work, stdio: 'inherit', shell: process.platform === 'win32' }).status ?? 1;

const status = run(['tsc', '--noEmit']) || run(['vitest', 'run', ...process.argv.slice(2)]);
if (status === 0) rmSync(work, { recursive: true, force: true });
else console.error(`\nSolutions failed - the run is kept in ${work}.`);
process.exit(status);
