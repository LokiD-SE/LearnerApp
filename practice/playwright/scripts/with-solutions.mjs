// Runs the tests against the reference solutions: copies the project to a temporary folder, puts
// solutions/ in place of exercises/, type-checks and runs Playwright there. Arguments go to Playwright.
// Usage: npm run test:solutions [-- playwright arguments]
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const work = mkdtempSync(join(tmpdir(), 'learnerapp-playwright-solutions-'));
const skip = /^(node_modules|test-results|playwright-report|exercises)(\/|\\|$)/;
cpSync(root, work, { recursive: true, filter: (source) => !skip.test(relative(root, source)) });
cpSync(join(root, 'solutions'), join(work, 'exercises'), { recursive: true });
symlinkSync(
  join(root, 'node_modules'),
  join(work, 'node_modules'),
  process.platform === 'win32' ? 'junction' : 'dir',
);

const env = { ...process.env, SHOP_DIR: resolve(root, '..', 'shop') };
const run = (args) =>
  spawnSync('npx', args, { cwd: work, stdio: 'inherit', env, shell: process.platform === 'win32' }).status ??
  1;

const status = run(['tsc', '--noEmit']) || run(['playwright', 'test', ...process.argv.slice(2)]);
if (status === 0) rmSync(work, { recursive: true, force: true });
else console.error(`\nSolutions failed - the run is kept in ${work} (test-results has traces).`);
process.exit(status);
