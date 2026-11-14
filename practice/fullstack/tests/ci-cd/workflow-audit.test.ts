import { auditWorkflow, type Finding } from '../../exercises/ci-cd/workflow-audit.js';

const PINNED_CHECKOUT = 'actions/checkout@11d5960a326750d5838078e36cf38b85af677262';
const PINNED_SETUP_NODE = 'actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020';

/** What the tests compare: the rule, job and step of every finding, in order (the detail is free text). */
const audit = (source: string) =>
  auditWorkflow(source).map(({ rule, job, step }: Finding) =>
    step === undefined ? { rule, job } : { rule, job, step },
  );

describe('auditing a workflow file', { tags: ['@exercise'] }, () => {
  test('a hardened workflow has no findings', () => {
    const source = `
name: CI
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: ${PINNED_CHECKOUT} # v4
      - uses: ${PINNED_SETUP_NODE} # v4
        with:
          node-version-file: .nvmrc
          cache: npm
      - uses: ./.github/actions/local-helper
      - run: npm ci
      - run: npm test
      - name: Check the title safely
        env:
          TITLE: \${{ github.event.pull_request.title }}
        run: echo "$TITLE"
`;
    expect(audit(source)).toEqual([]);
  });

  test('every remote action needs a full commit SHA - a tag, a branch or a short SHA is not enough', () => {
    const source = `
on: push
permissions: {}
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@main
      - uses: some-org/deploy-action/sub/path@v3.1.0
      - uses: some-org/other-action@11d5960
      - uses: docker://alpine:3.20
      - uses: ${PINNED_CHECKOUT}
  shared:
    uses: some-org/workflows/.github/workflows/release.yml@v2
  shared-pinned:
    uses: some-org/workflows/.github/workflows/release.yml@${'c'.repeat(40)}
`;
    expect(audit(source)).toEqual([
      { rule: 'unpinned-action', job: 'build', step: 1 },
      { rule: 'unpinned-action', job: 'build', step: 2 },
      { rule: 'unpinned-action', job: 'build', step: 3 },
      { rule: 'unpinned-action', job: 'build', step: 4 },
      { rule: 'unpinned-action', job: 'shared' },
    ]);
  });

  test('without a top-level permissions block, each job without one is reported; write-all is reported', () => {
    const source = `
on: push
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: npm run lint
  release:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: write-all
    steps:
      - run: npm publish
  docs:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - run: npm run docs
`;
    expect(audit(source)).toEqual([
      { rule: 'missing-permissions', job: 'lint' },
      { rule: 'broad-permissions', job: 'release' },
    ]);
  });

  test('write-all at the top is one finding for the whole workflow', () => {
    const source = `
on: push
permissions: write-all
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: npm test
`;
    expect(audit(source)).toEqual([{ rule: 'broad-permissions', job: '(workflow)' }]);
  });

  test('untrusted values expanded inside run: are script injections; trusted ones are not', () => {
    const source = `
on: [pull_request, issues]
permissions:
  contents: read
jobs:
  triage:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: echo "\${{ github.event.pull_request.title }}"
      - run: git switch \${{ github.head_ref }}
      - run: |
          echo "commit:"
          echo "\${{ github.event.head_commit.message }}"
      - run: echo "\${{ github.event.issue.body }}"
      - run: echo "\${{ github.event.pull_request.head.ref }}"
      - run: echo "\${{ github.sha }} \${{ github.event.pull_request.number }} \${{ github.run_id }}"
      - run: echo "$TITLE"
        env:
          TITLE: \${{ github.event.pull_request.title }}
`;
    expect(audit(source)).toEqual([
      { rule: 'script-injection', job: 'triage', step: 1 },
      { rule: 'script-injection', job: 'triage', step: 2 },
      { rule: 'script-injection', job: 'triage', step: 3 },
      { rule: 'script-injection', job: 'triage', step: 4 },
      { rule: 'script-injection', job: 'triage', step: 5 },
    ]);
  });

  test('pull_request_target checking out the pull request head is an untrusted checkout', () => {
    const source = `
on:
  pull_request_target:
    types: [opened, synchronize]
permissions:
  contents: read
jobs:
  preview:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: ${PINNED_CHECKOUT}
        with:
          ref: \${{ github.event.pull_request.head.sha }}
      - uses: ${PINNED_CHECKOUT}
`;
    expect(audit(source)).toEqual([{ rule: 'untrusted-checkout', job: 'preview', step: 1 }]);
  });

  test('the same checkout under pull_request is not privileged, so it is not reported', () => {
    const source = `
on: pull_request
permissions:
  contents: read
jobs:
  preview:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: ${PINNED_CHECKOUT}
        with:
          ref: \${{ github.event.pull_request.head.sha }}
`;
    expect(audit(source)).toEqual([]);
  });

  test('a job with steps needs timeout-minutes; a reusable-workflow call cannot have one', () => {
    const source = `
on: push
permissions:
  contents: read
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - run: npx playwright test
  release:
    uses: ./.github/workflows/release.yml
`;
    expect(audit(source)).toEqual([{ rule: 'no-timeout', job: 'e2e' }]);
  });

  test('findings come in file order and each has a detail', () => {
    const source = `
on: pull_request_target
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: \${{ github.head_ref }}
      - run: echo "\${{ github.event.pull_request.body }}"
`;
    expect(audit(source)).toEqual([
      { rule: 'missing-permissions', job: 'build' },
      { rule: 'no-timeout', job: 'build' },
      { rule: 'unpinned-action', job: 'build', step: 1 },
      { rule: 'untrusted-checkout', job: 'build', step: 1 },
      { rule: 'script-injection', job: 'build', step: 2 },
    ]);
    for (const finding of auditWorkflow(source)) expect(finding.detail.length).toBeGreaterThan(10);
  });
});
