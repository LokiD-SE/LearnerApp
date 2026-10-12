/**
 * Practice: an on-demand, adaptive and interleaved session built from what the learner has
 * studied (or from one lesson). Unlike Review, nothing has to be due - items are chosen by
 * need, and each one says why it was chosen.
 */
import { useState } from 'preact/hooks';
import type { ContentIndex } from '../../content/validate';
import type { MasteryLevel } from '../../domain/mastery';
import { buildPracticeSession, isEngaged, type PracticeItem } from '../../store/adaptive';
import { useProgress } from '../../store/ProgressContext';
import { masteryOf } from '../../store/selectors';
import { MasteryBadge, percent } from '../components/Badges';
import { ExerciseCard } from '../components/ExerciseCard';
import { href } from '../router';

export function PracticePage(props: { index: ContentIndex; lessonId?: string | undefined }) {
  // Each "Practise again" builds a fresh session by remounting it.
  const [round, setRound] = useState(0);
  return <PracticeSession key={round} {...props} onRestart={() => setRound((r) => r + 1)} />;
}

function PracticeSession({
  index,
  lessonId,
  onRestart,
}: {
  index: ContentIndex;
  lessonId?: string | undefined;
  onRestart: () => void;
}) {
  const { state, now } = useProgress();
  const scopeLesson = lessonId ? index.lessons.get(lessonId) : undefined;
  // The session is fixed when it starts, so answering an item doesn't reshuffle the rest.
  const [session] = useState<PracticeItem[]>(() =>
    buildPracticeSession(index, state, now(), scopeLesson ? { lessonId: scopeLesson.id } : {}),
  );
  const [before] = useState<Map<string, MasteryLevel>>(
    () =>
      new Map(session.map((item) => [item.conceptId, masteryOf(item.lesson, item.conceptId, state).level])),
  );
  const [position, setPosition] = useState(0);
  const [results, setResults] = useState<number[]>([]);
  const [answered, setAnswered] = useState(false);
  const title = scopeLesson ? `Practice: ${scopeLesson.title}` : 'Practice';

  if (lessonId && !scopeLesson) {
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Practice</h1>
        <p>
          There is no lesson called <code>{lessonId}</code>.{' '}
          <a href={href.practice()}>Practise everything you've studied</a>.
        </p>
      </section>
    );
  }

  if (session.length === 0) {
    const engaged = [...index.lessons.values()].some((lesson) => isEngaged(state, lesson));
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>{title}</h1>
        <div class="empty-state">
          {!engaged && !scopeLesson ? (
            <>
              <p>Practice builds on the lessons you have opened. Start a lesson first, then come back.</p>
              <a class="button primary" href={href.learn()}>
                Browse the curriculum
              </a>
            </>
          ) : (
            <>
              <p>Nothing to practise right now.</p>
              <p class="muted">
                Everything here is either mastered or was answered in the last few minutes. Check your review
                queue, or come back later.
              </p>
              <a class="button primary" href={href.review()}>
                Go to your reviews
              </a>
            </>
          )}
        </div>
      </section>
    );
  }

  if (position >= session.length) {
    const average = results.reduce((sum, r) => sum + r, 0) / Math.max(results.length, 1);
    const concepts = [...new Map(session.map((item) => [item.conceptId, item])).values()];
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Practice complete</h1>
        <p>
          You practised {results.length} {results.length === 1 ? 'item' : 'items'} with an average of{' '}
          {percent(average)}.
        </p>
        <h2>Where you stand now</h2>
        <ul class="practice-summary">
          {concepts.map((item) => {
            const was = before.get(item.conceptId)!;
            const current = masteryOf(item.lesson, item.conceptId, state).level;
            return (
              <li key={item.conceptId}>
                <strong>{item.conceptName}</strong>{' '}
                {was !== current ? (
                  <>
                    <MasteryBadge level={was} /> → <MasteryBadge level={current} />
                  </>
                ) : (
                  <MasteryBadge level={current} />
                )}
              </li>
            );
          })}
        </ul>
        <div class="row">
          <button type="button" class="button primary" onClick={onRestart}>
            Practise again
          </button>
          <a class="button ghost" href={href.progress()}>
            See your progress
          </a>
        </div>
      </section>
    );
  }

  const item = session[position]!;
  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>{title}</h1>
      <p class="muted">
        Item {position + 1} of {session.length} · from{' '}
        <a href={href.lesson(item.lesson.id)}>{item.lesson.title}</a>
      </p>
      <progress max={session.length} value={position} aria-label="Practice progress" />
      <p class="practice-reason">
        <strong>{item.conceptName}:</strong> {item.reason}
      </p>
      <div key={`${item.lesson.id}/${item.exercise.id}`} class="review-item">
        <ExerciseCard
          lesson={item.lesson}
          exercise={item.exercise}
          mode="practice"
          practice={index.curriculum.practice}
          onRecorded={(credit) => {
            setResults((r) => [...r, credit]);
            setAnswered(true);
          }}
        />
      </div>
      <div class="row">
        <button
          type="button"
          class="button primary"
          disabled={!answered}
          onClick={() => {
            setAnswered(false);
            setPosition((p) => p + 1);
            window.scrollTo(0, 0);
          }}
        >
          {position + 1 === session.length ? 'Finish' : 'Next item'}
        </button>
        {!answered && <span class="hint-text">Answer to continue.</span>}
      </div>
    </section>
  );
}
