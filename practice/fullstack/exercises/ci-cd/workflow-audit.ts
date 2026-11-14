// Exercise: a small linter for GitHub Actions workflow files. Tests: tests/ci-cd/workflow-audit.test.ts
//
// This first draft only flags actions that follow a branch (@main, @master). Make it report every
// finding below, one Finding per problem, in file order (jobs in order, steps in order):
//   1. unpinned-action - a step's `uses:` or a job's `uses:` (a reusable workflow) that names
//      owner/repo[/path]@ref where ref is not a full 40-character commit SHA (a tag such as @v4 can be
//      moved). Local actions (./...) and docker:// images are out of scope - skip them.
//   2. missing-permissions - a job with no `permissions:` when the workflow has none at the top either
//      (one finding per such job).
//   3. broad-permissions - `permissions: write-all`, at the top (job "(workflow)") or on a job.
//   4. script-injection - a step's `run:` that expands an untrusted value inside ${{ }}: github.head_ref,
//      or a github.event... path ending in body, default_branch, email, head_ref, label, message, name,
//      page_name, ref or title (GitHub's "Script injections" list).
//   5. untrusted-checkout - the workflow is triggered by pull_request_target and a step uses
//      actions/checkout with a `ref` built from github.event.pull_request.head... or github.head_ref.
//   6. no-timeout - a job with steps and no `timeout-minutes` (the default is 360 minutes). A job that
//      calls a reusable workflow (job-level `uses:`) can't have one - skip it.
// `step` is the 1-based position of the step in its job; leave it out for job-level findings.

import { parse } from 'yaml';

export type Rule =
  | 'unpinned-action'
  | 'missing-permissions'
  | 'broad-permissions'
  | 'script-injection'
  | 'untrusted-checkout'
  | 'no-timeout';

export interface Finding {
  rule: Rule;
  /** The job id, or "(workflow)" for a finding about the top level of the file. */
  job: string;
  /** 1-based position of the step in the job, when the finding is about one step. */
  step?: number;
  /** A sentence a reviewer can act on. */
  detail: string;
}

type Mapping = Record<string, unknown>;

const isMapping = (value: unknown): value is Mapping =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export function auditWorkflow(source: string): Finding[] {
  const workflow: unknown = parse(source);
  if (!isMapping(workflow) || !isMapping(workflow.jobs)) throw new Error('not a workflow: no jobs');

  const findings: Finding[] = [];
  for (const [jobId, job] of Object.entries(workflow.jobs)) {
    if (!isMapping(job) || !Array.isArray(job.steps)) continue;
    job.steps.forEach((step: unknown, index) => {
      if (!isMapping(step) || typeof step.uses !== 'string') return;
      if (step.uses.endsWith('@main') || step.uses.endsWith('@master')) {
        findings.push({
          rule: 'unpinned-action',
          job: jobId,
          step: index + 1,
          detail: `${step.uses} follows a branch`,
        });
      }
    });
  }
  return findings;
}
