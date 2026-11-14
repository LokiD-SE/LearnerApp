// Exercise: the gate in front of SandPay's (fictional) deploy job. Tests: tests/ci-cd/deploy-gate.test.ts
//
// The deploy job calls decideDeploy before it ships anything. This first draft has shipped things it
// shouldn't. Fix it so that, checking in this order:
//   1. only push and workflow_dispatch runs deploy - anything else is 'wrong-event';
//   2. only refs/heads/main deploys - else 'wrong-ref';
//   3. every job in needs must be 'success' (skipped and cancelled jobs proved nothing), and an empty
//      needs proves nothing either - else 'checks-not-green';
//   4. the artifact must exist and be built from this run's sha (build once, deploy that) - else
//      'artifact-mismatch';
//   5. production only: staging must have run the same artifact DIGEST and its smoke test passed - else
//      'not-proven-on-staging';
//   6. production only: not inside a change freeze [from, to) - else 'change-freeze'.

/** The results a job can see for the jobs it `needs` (GitHub's needs.<job_id>.result values). */
export type JobResult = 'success' | 'failure' | 'cancelled' | 'skipped';

export interface BuiltArtifact {
  /** The commit the artifact was built from. */
  sha: string;
  /** The content digest of the artifact (for an image, sha256:...) - what is actually deployed. */
  digest: string;
}

export interface DeployRequest {
  /** github.event_name of the run that wants to deploy. */
  event: string;
  /** github.ref, e.g. refs/heads/main or refs/pull/42/merge. */
  ref: string;
  /** The commit this run is for (github.sha). */
  sha: string;
  target: 'staging' | 'production';
  /** Results of every job the deploy job needs - test, lint, build... */
  needs: Record<string, JobResult>;
  /** What the build job produced, or null if it produced nothing. */
  artifact: BuiltArtifact | null;
  /** The latest staging deployment and its smoke test - production only ships what staging proved. */
  staging: (BuiltArtifact & { smoke: 'passed' | 'failed' }) | null;
  /** Change-freeze windows, team policy: [from, to) - from inclusive, to exclusive. */
  freezes: { from: Date; to: Date }[];
  now: Date;
}

export type DeployDecision =
  | { deploy: true }
  | {
      deploy: false;
      reason:
        | 'wrong-event'
        | 'wrong-ref'
        | 'checks-not-green'
        | 'artifact-mismatch'
        | 'not-proven-on-staging'
        | 'change-freeze';
    };

export function decideDeploy(r: DeployRequest): DeployDecision {
  if (r.event === 'pull_request') return { deploy: false, reason: 'wrong-event' };
  if (!r.ref.endsWith('main')) return { deploy: false, reason: 'wrong-ref' };
  if (Object.values(r.needs).includes('failure')) return { deploy: false, reason: 'checks-not-green' };
  if (r.target === 'production' && r.staging?.sha !== r.sha) {
    return { deploy: false, reason: 'not-proven-on-staging' };
  }
  return { deploy: true };
}
