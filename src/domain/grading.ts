/**
 * Scores in [0, 1] for each exercise type, and the credit a score earns after hints.
 * The rules are documented in docs/MASTERY_MODEL.md; change both together.
 */

export interface SelectionResult {
  score: number;
  /** picked and correct */
  hits: string[];
  /** picked but wrong */
  wrong: string[];
  /** correct but not picked */
  missed: string[];
}

/** Multiple choice and "pick the faulty lines": every wrong pick cancels a right one. */
export function gradeSelection(selected: readonly string[], correct: readonly string[]): SelectionResult {
  const picked = new Set(selected);
  const answer = new Set(correct);
  const hits = [...picked].filter((id) => answer.has(id));
  const wrong = [...picked].filter((id) => !answer.has(id));
  const missed = [...answer].filter((id) => !picked.has(id));
  const score = answer.size === 0 ? 0 : Math.max(0, (hits.length - wrong.length) / answer.size);
  return { score, hits, wrong, missed };
}

/** Ordering: the share of items in their correct position. */
export function gradeOrder(submitted: readonly string[], correctOrder: readonly string[]): number {
  if (correctOrder.length === 0 || submitted.length !== correctOrder.length) return 0;
  const inPlace = correctOrder.filter((id, index) => submitted[index] === id).length;
  return inPlace / correctOrder.length;
}

/** Self-assessed answers: the share of rubric points the learner says they covered. */
export function gradeRubric(covered: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(1, Math.max(0, covered / total));
}

export const HINT_PENALTY = 0.15;
export const MAX_HINT_PENALTY = 0.45;

/** Each hint taken before answering removes 15% of the credit, at most 45%. */
export function creditFor(score: number, hintsUsed: number): number {
  const penalty = Math.min(Math.max(0, hintsUsed) * HINT_PENALTY, MAX_HINT_PENALTY);
  return roundScore(Math.min(1, Math.max(0, score)) * (1 - penalty));
}

export const roundScore = (value: number) => Math.round(value * 1000) / 1000;
