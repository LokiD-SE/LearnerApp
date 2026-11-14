import { decideDeploy, type DeployRequest } from '../../exercises/ci-cd/deploy-gate.js';

const SHA = 'a'.repeat(40);
const OTHER_SHA = 'b'.repeat(40);
const DIGEST = 'sha256:' + '1'.repeat(64);
const OTHER_DIGEST = 'sha256:' + '2'.repeat(64);
const NOW = new Date('2026-11-14T10:00:00Z');

/** A request that should deploy to production; each test changes one thing. */
function request(change: Partial<DeployRequest> = {}): DeployRequest {
  return {
    event: 'push',
    ref: 'refs/heads/main',
    sha: SHA,
    target: 'production',
    needs: { lint: 'success', test: 'success', build: 'success' },
    artifact: { sha: SHA, digest: DIGEST },
    staging: { sha: SHA, digest: DIGEST, smoke: 'passed' },
    freezes: [],
    now: NOW,
    ...change,
  };
}

describe('the deploy gate', { tags: ['@exercise'] }, () => {
  test('a green push to main with a proven artifact deploys to production and staging', () => {
    expect(decideDeploy(request())).toEqual({ deploy: true });
    expect(decideDeploy(request({ target: 'staging', staging: null }))).toEqual({ deploy: true });
    expect(decideDeploy(request({ event: 'workflow_dispatch' }))).toEqual({ deploy: true });
  });

  test.each(['pull_request', 'pull_request_target', 'schedule', 'workflow_run'])(
    'a %s run never deploys',
    (event) => {
      expect(decideDeploy(request({ event }))).toEqual({ deploy: false, reason: 'wrong-event' });
    },
  );

  test.each(['refs/heads/feature/main', 'refs/heads/domain', 'refs/pull/42/merge', 'refs/tags/main'])(
    'only refs/heads/main deploys, not %s',
    (ref) => {
      expect(decideDeploy(request({ ref }))).toEqual({ deploy: false, reason: 'wrong-ref' });
    },
  );

  test.each(['failure', 'cancelled', 'skipped'] as const)('a %s job in needs blocks the deploy', (result) => {
    const needs = { lint: 'success', test: result, build: 'success' } as const;
    expect(decideDeploy(request({ needs }))).toEqual({ deploy: false, reason: 'checks-not-green' });
  });

  test('a deploy job that needs nothing has proved nothing', () => {
    expect(decideDeploy(request({ needs: {} }))).toEqual({ deploy: false, reason: 'checks-not-green' });
  });

  test('only the artifact built from this commit is deployed', () => {
    expect(decideDeploy(request({ artifact: null }))).toEqual({ deploy: false, reason: 'artifact-mismatch' });
    expect(decideDeploy(request({ artifact: { sha: OTHER_SHA, digest: DIGEST } }))).toEqual({
      deploy: false,
      reason: 'artifact-mismatch',
    });
    expect(
      decideDeploy(
        request({ target: 'staging', staging: null, artifact: { sha: OTHER_SHA, digest: DIGEST } }),
      ),
    ).toEqual({ deploy: false, reason: 'artifact-mismatch' });
  });

  test('production ships only the digest that passed on staging', () => {
    expect(decideDeploy(request({ staging: null }))).toEqual({
      deploy: false,
      reason: 'not-proven-on-staging',
    });
    // Same commit, rebuilt: different bytes were tested on staging.
    expect(decideDeploy(request({ staging: { sha: SHA, digest: OTHER_DIGEST, smoke: 'passed' } }))).toEqual({
      deploy: false,
      reason: 'not-proven-on-staging',
    });
    expect(decideDeploy(request({ staging: { sha: SHA, digest: DIGEST, smoke: 'failed' } }))).toEqual({
      deploy: false,
      reason: 'not-proven-on-staging',
    });
  });

  test('a change freeze blocks production from its start up to (not including) its end', () => {
    const freeze = (from: string, to: string) => [{ from: new Date(from), to: new Date(to) }];
    expect(
      decideDeploy(request({ freezes: freeze('2026-11-14T10:00:00Z', '2026-11-15T00:00:00Z') })),
    ).toEqual({
      deploy: false,
      reason: 'change-freeze',
    });
    expect(
      decideDeploy(request({ freezes: freeze('2026-11-13T00:00:00Z', '2026-11-14T10:00:00Z') })),
    ).toEqual({
      deploy: true,
    });
    expect(
      decideDeploy(
        request({
          target: 'staging',
          staging: null,
          freezes: freeze('2026-11-14T00:00:00Z', '2026-11-15T00:00:00Z'),
        }),
      ),
    ).toEqual({ deploy: true });
  });

  test('the checks run in order - the first broken rule is the reason', () => {
    expect(decideDeploy(request({ event: 'pull_request', ref: 'refs/pull/42/merge' }))).toEqual({
      deploy: false,
      reason: 'wrong-event',
    });
    expect(decideDeploy(request({ needs: { test: 'failure' }, artifact: null }))).toEqual({
      deploy: false,
      reason: 'checks-not-green',
    });
    expect(decideDeploy(request({ artifact: { sha: OTHER_SHA, digest: OTHER_DIGEST } }))).toEqual({
      deploy: false,
      reason: 'artifact-mismatch',
    });
  });
});
