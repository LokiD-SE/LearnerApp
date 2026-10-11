import type { Level, Skill } from '../../content/schema';
import { MASTERY_LABEL, type MasteryLevel } from '../../domain/mastery';
import { LESSON_STATUS_LABEL, type LessonStatus } from '../../store/selectors';

export const LevelBadge = ({ level }: { level: Level }) => (
  <span class={`badge badge-level badge-${level}`}>{level}</span>
);

export const StatusBadge = ({ status }: { status: LessonStatus }) => (
  <span class={`badge badge-status status-${status}`}>{LESSON_STATUS_LABEL[status]}</span>
);

export const MasteryBadge = ({ level }: { level: MasteryLevel }) => (
  <span class={`badge badge-mastery mastery-${level}`}>{MASTERY_LABEL[level]}</span>
);

const SKILL_LABEL: Record<Skill, string> = {
  recognition: 'Recognition',
  recall: 'Recall',
  application: 'Application',
  analysis: 'Analysis',
};
export const SkillBadge = ({ skill }: { skill: Skill }) => (
  <span class={`badge badge-skill skill-${skill}`}>{SKILL_LABEL[skill]}</span>
);

export const percent = (value: number) => `${Math.round(value * 100)}%`;

export function formatDate(iso: string | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}
