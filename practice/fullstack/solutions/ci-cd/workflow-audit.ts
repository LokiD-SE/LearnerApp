// Exercise: a small linter for GitHub Actions workflow files. Tests: tests/ci-cd/workflow-audit.test.ts
//
// Reference solution. The rules follow GitHub's "Secure use reference", "Script injections" and
// "Workflow syntax" documentation (checked November 2026).

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

/** A full-length commit SHA: 40 hexadecimal characters. A tag or branch can be moved; a commit can't. */
const FULL_SHA = /^[0-9a-f]{40}$/;

/**
 * Expressions reading values an outsider can choose - a pull request title or body, a branch name,
 * a commit message, an e-mail address... ("Script injections": contexts that typically end in body,
 * default_branch, email, head_ref, label, message, name, page_name, ref and title).
 */
const UNTRUSTED_EXPRESSION =
  /\$\{\{[^}]*\b(github\.head_ref|github\.event\.[\w.*[\]'"-]*\b(body|default_branch|email|head_ref|label|message|name|page_name|ref|title))\b[^}]*\}\}/;

/** Remote actions and reusable workflows look like owner/repo[/path]@ref; local and docker ones don't. */
function unpinnedReference(uses: unknown): string | undefined {
  if (typeof uses !== 'string' || uses.startsWith('./') || uses.startsWith('docker://')) return undefined;
  const at = uses.lastIndexOf('@');
  if (at < 0) return uses; // no ref at all
  return FULL_SHA.test(uses.slice(at + 1)) ? undefined : uses;
}

function triggers(on: unknown): string[] {
  if (typeof on === 'string') return [on];
  if (Array.isArray(on)) return on.map(String);
  if (isMapping(on)) return Object.keys(on);
  return [];
}

export function auditWorkflow(source: string): Finding[] {
  const workflow: unknown = parse(source);
  if (!isMapping(workflow) || !isMapping(workflow.jobs)) throw new Error('not a workflow: no jobs');

  const findings: Finding[] = [];
  const topLevelPermissions = 'permissions' in workflow;
  const privilegedTrigger = triggers(workflow.on).includes('pull_request_target');

  if (workflow.permissions === 'write-all') {
    findings.push({
      rule: 'broad-permissions',
      job: '(workflow)',
      detail: 'permissions: write-all gives every job every write scope - grant only what each job needs',
    });
  }

  for (const [jobId, job] of Object.entries(workflow.jobs)) {
    if (!isMapping(job)) continue;

    if (job.permissions === 'write-all') {
      findings.push({ rule: 'broad-permissions', job: jobId, detail: 'permissions: write-all on the job' });
    }
    if (!topLevelPermissions && !('permissions' in job)) {
      findings.push({
        rule: 'missing-permissions',
        job: jobId,
        detail: 'no permissions block here or at the top, so GITHUB_TOKEN gets the repository default',
      });
    }

    // A job that calls a reusable workflow has no steps and no timeout-minutes of its own.
    if ('uses' in job) {
      const ref = unpinnedReference(job.uses);
      if (ref)
        findings.push({
          rule: 'unpinned-action',
          job: jobId,
          detail: `${ref} is not pinned to a commit SHA`,
        });
      continue;
    }

    if (!('timeout-minutes' in job)) {
      findings.push({
        rule: 'no-timeout',
        job: jobId,
        detail: 'no timeout-minutes - a hung job runs for the default 360 minutes',
      });
    }

    const steps = Array.isArray(job.steps) ? job.steps : [];
    steps.forEach((step: unknown, index) => {
      if (!isMapping(step)) return;
      const position = index + 1;

      const ref = unpinnedReference(step.uses);
      if (ref) {
        findings.push({
          rule: 'unpinned-action',
          job: jobId,
          step: position,
          detail: `${ref} is not pinned to a commit SHA`,
        });
      }

      if (typeof step.run === 'string' && UNTRUSTED_EXPRESSION.test(step.run)) {
        findings.push({
          rule: 'script-injection',
          job: jobId,
          step: position,
          detail: 'an untrusted value is expanded into the script - pass it through env: and quote "$VAR"',
        });
      }

      const checkout = typeof step.uses === 'string' && step.uses.startsWith('actions/checkout@');
      const checkoutRef = isMapping(step.with) ? String(step.with.ref ?? '') : '';
      if (
        privilegedTrigger &&
        checkout &&
        /github\.event\.pull_request\.head\.|github\.head_ref/.test(checkoutRef)
      ) {
        findings.push({
          rule: 'untrusted-checkout',
          job: jobId,
          step: position,
          detail: 'pull_request_target checks out the pull request head - untrusted code runs with secrets',
        });
      }
    });
  }
  return findings;
}
