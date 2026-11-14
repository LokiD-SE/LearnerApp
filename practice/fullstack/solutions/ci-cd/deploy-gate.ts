// Exercise: the gate in front of SandPay's (fictional) deploy job. Tests: tests/ci-cd/deploy-gate.test.ts
//
// Reference solution.

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

const DEPLOYING_EVENTS = new Set(['push', 'workflow_dispatch']);
const MAIN = 'refs/heads/main';

export function decideDeploy(r: DeployRequest): DeployDecision {
  // Pull requests (and pull_request_target, schedule...) never deploy, whatever the branch.
  if (!DEPLOYING_EVENTS.has(r.event)) return { deploy: false, reason: 'wrong-event' };
  if (r.ref !== MAIN) return { deploy: false, reason: 'wrong-ref' };

  // Only success is green: skipped and cancelled jobs proved nothing. No needs at all proves nothing too.
  const results = Object.values(r.needs);
  if (results.length === 0 || results.some((result) => result !== 'success')) {
    return { deploy: false, reason: 'checks-not-green' };
  }

  // Build once: deploy the artifact built (and tested) from this very commit.
  if (!r.artifact || r.artifact.sha !== r.sha) return { deploy: false, reason: 'artifact-mismatch' };

  if (r.target === 'production') {
    // The digest, not the commit: the same commit rebuilt can give different bytes.
    if (!r.staging || r.staging.digest !== r.artifact.digest || r.staging.smoke !== 'passed') {
      return { deploy: false, reason: 'not-proven-on-staging' };
    }
    const now = r.now.getTime();
    if (r.freezes.some((f) => now >= f.from.getTime() && now < f.to.getTime())) {
      return { deploy: false, reason: 'change-freeze' };
    }
  }
  return { deploy: true };
}
