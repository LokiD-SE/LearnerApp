// Shared by both rest-design exercises - you don't need to change this file.
// Errors are Problem Details (RFC 9457): an application/problem+json body with type, title, status,
// optional detail and instance, and extension members of our own.
import type { Response } from 'express';

/** Base URI for SandPay's problem types. Each type is a stable identifier clients can compare. */
export const PROBLEMS = 'https://api.sandpay.example/problems/';

export interface Problem {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  [extension: string]: unknown;
}

export function sendProblem(res: Response, problem: Problem): void {
  res.status(problem.status).type('application/problem+json').json(problem);
}
