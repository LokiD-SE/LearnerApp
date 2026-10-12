import { useState } from 'preact/hooks';
import type { ContentIndex } from '../../content/validate';
import { useProgress } from '../../store/ProgressContext';
import { dueReviews, nextDueDate, type ReviewItem } from '../../store/selectors';
import { formatDate, percent } from '../components/Badges';
import { ExerciseCard } from '../components/ExerciseCard';
import { RecallCardView } from '../components/RecallCard';
import { href } from '../router';

export function ReviewPage({ index }: { index: ContentIndex }) {
  const { state, now } = useProgress();
  // The session works on the items due when it started, so answering one (which
  // reschedules it) doesn't reshuffle the queue under the learner.
  const [session] = useState<ReviewItem[]>(() => dueReviews(index, state, now()));
  const [position, setPosition] = useState(0);
  const [results, setResults] = useState<number[]>([]);
  const [answered, setAnswered] = useState(false);

  if (session.length === 0) {
    const next = nextDueDate(index, state, now());
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Review</h1>
        <div class="empty-state">
          <p>Nothing is due right now.</p>
          <p class="muted">
            {next
              ? `The next item is due on ${formatDate(next.toISOString())}.`
              : 'Mark a lesson as read or answer its exercises, and they will come back here on a spaced schedule.'}
          </p>
          <a class="button primary" href={href.learn()}>
            Continue learning
          </a>
        </div>
      </section>
    );
  }

  if (position >= session.length) {
    const average = results.reduce((sum, r) => sum + r, 0) / Math.max(results.length, 1);
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Review complete</h1>
        <p>
          You reviewed {results.length} {results.length === 1 ? 'item' : 'items'} with an average of{' '}
          {percent(average)}. Items you found hard come back sooner; easy ones wait longer.
        </p>
        <a class="button primary" href={href.home()}>
          Back to home
        </a>
      </section>
    );
  }

  const item = session[position]!;
  const onRecorded = (credit: number) => {
    setResults((r) => [...r, credit]);
    setAnswered(true);
  };

  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>Review</h1>
      <p class="muted">
        Item {position + 1} of {session.length} · from{' '}
        <a href={href.lesson(item.lesson.id)}>{item.lesson.title}</a>
      </p>
      <progress max={session.length} value={position} aria-label="Review progress" />
      <div key={item.key} class="review-item">
        {item.kind === 'exercise' ? (
          <ExerciseCard
            lesson={item.lesson}
            exercise={item.exercise}
            mode="review"
            practice={index.curriculum.practice}
            onRecorded={onRecorded}
          />
        ) : (
          <RecallCardView lesson={item.lesson} card={item.card} mode="review" onRecorded={onRecorded} />
        )}
      </div>
      <div class="row">
        <button
          type="button"
          class="button primary"
          disabled={!answered}
          onClick={() => {
            setAnswered(false);
            setPosition((p) => p + 1);
          }}
        >
          {position + 1 === session.length ? 'Finish' : 'Next item'}
        </button>
        {!answered && <span class="hint-text">Answer to continue.</span>}
      </div>
    </section>
  );
}
