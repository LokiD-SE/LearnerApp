/**
 * Mastery by concept. One right answer is not mastery: the model weighs what kind of
 * evidence there is (recognising < recalling < applying / analysing), discounts hints and
 * self-assessment, needs practical success, and only calls a concept mastered once it has
 * been recalled again after a gap. Documented in docs/MASTERY_MODEL.md.
 */
import type { Skill } from '../content/schema';

export const SKILL_WEIGHT: Record<Skill, number> = { recognition: 1, recall: 2, application: 3, analysis: 3 };
export const SELF_ASSESSED_FACTOR = 0.8;
export const PRACTISING_SCORE = 0.6;
export const PROFICIENT_SCORE = 0.8;
export const PROFICIENT_COVERAGE = 0.75;
export const RETENTION_GAP_MS = 24 * 60 * 60 * 1000;

export const MASTERY_LEVELS = ['not-started', 'attempted', 'practising', 'proficient', 'mastered'] as const;
export type MasteryLevel = (typeof MASTERY_LEVELS)[number];

export const MASTERY_LABEL: Record<MasteryLevel, string> = {
  'not-started': 'Not started',
  attempted: 'Attempted',
  practising: 'Practising',
  proficient: 'Proficient',
  mastered: 'Mastered',
};

/** One graded item that teaches a concept: an exercise or a recall card. */
export interface ConceptItem {
  key: string;
  skill: Skill;
}

export interface Evidence {
  key: string;
  skill: Skill;
  /** score after the hint penalty, 0..1 */
  credit: number;
  selfAssessed: boolean;
  mode: 'lesson' | 'review';
  at: string;
  /** Retries straight after feedback are practice, not evidence. */
  firstTry: boolean;
}

export interface ConceptMastery {
  level: MasteryLevel;
  /** weighted score of the latest first-try evidence per item, 0..1 */
  score: number;
  /** share of the concept's item weight with any evidence, 0..1 */
  coverage: number;
  /** true when an application/analysis item scored >= PROFICIENT_SCORE (or the concept has none) */
  practical: boolean;
  /** true after a good review at least RETENTION_GAP_MS after the first evidence */
  retained: boolean;
  itemsAttempted: number;
  itemsTotal: number;
}

const isPractical = (skill: Skill) => skill === 'application' || skill === 'analysis';

export function conceptMastery(items: readonly ConceptItem[], evidence: readonly Evidence[]): ConceptMastery {
  const itemSkill = new Map(items.map((item) => [item.key, item.skill]));
  const firstTries = evidence.filter((e) => e.firstTry && itemSkill.has(e.key));

  const latest = new Map<string, Evidence>();
  for (const e of [...firstTries].sort((a, b) => a.at.localeCompare(b.at))) latest.set(e.key, e);

  let weighted = 0;
  let weightSum = 0;
  for (const e of latest.values()) {
    const weight = SKILL_WEIGHT[e.skill] * (e.selfAssessed ? SELF_ASSESSED_FACTOR : 1);
    weighted += weight * e.credit;
    weightSum += weight;
  }
  const score = weightSum === 0 ? 0 : Math.round((weighted / weightSum) * 1000) / 1000;

  const totalWeight = items.reduce((sum, item) => sum + SKILL_WEIGHT[item.skill], 0);
  const coveredWeight = [...latest.keys()].reduce((sum, key) => sum + SKILL_WEIGHT[itemSkill.get(key)!], 0);
  const coverage = totalWeight === 0 ? 0 : Math.round((coveredWeight / totalWeight) * 1000) / 1000;

  const hasPracticalItems = items.some((item) => isPractical(item.skill));
  const practical =
    !hasPracticalItems ||
    [...latest.values()].some((e) => isPractical(e.skill) && e.credit >= PROFICIENT_SCORE);

  const firstAt = firstTries.length ? Math.min(...firstTries.map((e) => Date.parse(e.at))) : NaN;
  const retained = firstTries.some(
    (e) =>
      e.mode === 'review' && e.credit >= PROFICIENT_SCORE && Date.parse(e.at) - firstAt >= RETENTION_GAP_MS,
  );

  let level: MasteryLevel = 'not-started';
  if (latest.size > 0) {
    if (score >= PROFICIENT_SCORE && coverage >= PROFICIENT_COVERAGE && practical) {
      level = retained ? 'mastered' : 'proficient';
    } else if (score >= PRACTISING_SCORE) level = 'practising';
    else level = 'attempted';
  }
  return {
    level,
    score,
    coverage,
    practical,
    retained,
    itemsAttempted: latest.size,
    itemsTotal: items.length,
  };
}
