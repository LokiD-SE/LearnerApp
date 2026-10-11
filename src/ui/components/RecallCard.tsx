/**
 * Active recall: answer from memory, reveal, then say honestly how well you knew it.
 * The self-grade feeds the review schedule and (as weak, self-assessed evidence) mastery.
 */
import { useState } from 'preact/hooks';
import type { Lesson, RecallCard as Card } from '../../content/schema';
import { intervalDays } from '../../domain/srs';
import { useProgress } from '../../store/ProgressContext';
import { itemKey, recordAttempt } from '../../store/state';
import { Markdown } from './Markdown';

const GRADES = [
  { label: "Didn't know it", score: 0 },
  { label: 'Partly', score: 0.6 },
  { label: 'Knew it', score: 1 },
] as const;

export function RecallCardView(props: {
  lesson: Lesson;
  card: Card;
  mode: 'lesson' | 'review';
  onRecorded?: (credit: number) => void;
}) {
  const { lesson, card, mode, onRecorded } = props;
  const { state, update } = useProgress();
  const [revealed, setRevealed] = useState(false);
  const [graded, setGraded] = useState<string | undefined>();
  const [gradedOnce, setGradedOnce] = useState(false);
  const scheduled = state.reviews[itemKey(lesson.id, card.id)];

  const grade = (label: string, score: number) => {
    const firstTry = !gradedOnce;
    update((s, now) =>
      recordAttempt(
        s,
        {
          lesson,
          itemId: card.id,
          kind: 'recall',
          concept: card.concept,
          skill: 'recall',
          score,
          hintsUsed: 0,
          selfAssessed: true,
          firstTry,
          mode,
        },
        now,
      ),
    );
    setGraded(label);
    setGradedOnce(true);
    onRecorded?.(score);
  };

  return (
    <div class="recall-card">
      <Markdown source={card.prompt} class="recall-prompt" />
      {!revealed ? (
        <button type="button" class="button secondary" onClick={() => setRevealed(true)}>
          Show answer
        </button>
      ) : (
        <>
          <div class="recall-answer">
            <Markdown source={card.answer} />
          </div>
          {graded ? (
            <p class="recall-saved" aria-live="polite">
              Saved as "{graded}".{' '}
              {mode === 'lesson' &&
                scheduled &&
                `Next review in ${intervalDays(scheduled.box)} day${intervalDays(scheduled.box) === 1 ? '' : 's'}.`}
            </p>
          ) : (
            <div class="recall-grades" role="group" aria-label="How well did you know it?">
              {GRADES.map((g) => (
                <button
                  key={g.label}
                  type="button"
                  class="button secondary"
                  onClick={() => grade(g.label, g.score)}
                >
                  {g.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
