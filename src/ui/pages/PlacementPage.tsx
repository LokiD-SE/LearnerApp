/**
 * Placement test: show what you already know so you can skip it.
 *
 * Questions come one at a time with no hints and no feedback until the end. A lesson is
 * "tested out" only when every one of its placement questions is answered fully correctly;
 * "I don't know this yet" is offered so a lucky guess doesn't skip a lesson you need.
 */
import { useEffect, useRef, useState } from 'preact/hooks';
import type { Lesson } from '../../content/schema';
import type { ContentIndex } from '../../content/validate';
import { useProgress } from '../../store/ProgressContext';
import { placementItems, type PlacementItem } from '../../store/selectors';
import { recordPlacement } from '../../store/state';
import { StatusBadge, formatDate } from '../components/Badges';
import { DebugBody, McqBody, OrderBody, type SubmitArgs } from '../components/ExerciseCard';
import { Markdown } from '../components/Markdown';
import { href } from '../router';

interface Answer {
  item: PlacementItem;
  score: number;
  dontKnow: boolean;
}

const MINUTES_PER_QUESTION = 1.5;

export function PlacementPage({
  index,
  kind,
  id,
}: {
  index: ContentIndex;
  kind: 'path' | 'lesson';
  id: string;
}) {
  const { state, update } = useProgress();
  const [phase, setPhase] = useState<'intro' | 'questions' | 'results'>('intro');
  const [answers, setAnswers] = useState<Answer[]>([]);
  const questionHeading = useRef<HTMLHeadingElement>(null);

  const path = kind === 'path' ? index.curriculum.paths.find((p) => p.id === id) : undefined;
  const lesson = kind === 'lesson' ? index.lessons.get(id) : undefined;
  const items = placementItems(index, { kind, id });
  const lessons = [...new Map(items.map((item) => [item.lesson.id, item.lesson])).values()];
  const title = path
    ? `Placement test: ${path.title}`
    : lesson
      ? `Test out: ${lesson.title}`
      : 'Placement test';

  useEffect(() => {
    if (phase === 'questions') questionHeading.current?.focus();
    else window.scrollTo(0, 0);
  }, [phase, answers.length]);

  if (!path && !lesson) {
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Placement test not found</h1>
        <p>
          There is no learning path or lesson called <code>{id}</code>.{' '}
          <a href={href.learn()}>Browse the curriculum</a>.
        </p>
      </section>
    );
  }

  if (items.length === 0) {
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>{title}</h1>
        <div class="empty-state">
          <p>There are no placement questions for this {kind} yet.</p>
          <a class="button secondary" href={lesson ? href.lesson(lesson.id) : href.learn()}>
            {lesson ? 'Back to the lesson' : 'Browse the curriculum'}
          </a>
        </div>
      </section>
    );
  }

  const answer = (score: number, dontKnow: boolean) => {
    const item = items[answers.length]!;
    const next = [...answers, { item, score, dontKnow }];
    setAnswers(next);
    if (next.length < items.length) return;
    // Nothing is saved until the last answer: leaving half-way leaves no partial result.
    update((current, now) =>
      lessons.reduce(
        (acc, l) =>
          recordPlacement(
            acc,
            l,
            next
              .filter((a) => a.item.lesson.id === l.id)
              .map((a) => ({ questionId: a.item.question.id, score: a.score })),
            kind,
            now,
          ),
        current,
      ),
    );
    setPhase('results');
  };

  if (phase === 'intro') {
    const previous = lessons
      .map((l) => state.placements[l.id]?.at)
      .filter((at): at is string => Boolean(at))
      .sort()
      .at(-1);
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>{title}</h1>
        <p class="lead">
          Show what you already know, so you can skip it and spend your time where it counts.
        </p>
        <ul class="placement-rules">
          <li>
            {items.length} questions from {lessons.length} {lessons.length === 1 ? 'lesson' : 'lessons'},
            about {Math.ceil(items.length * MINUTES_PER_QUESTION)} minutes.
          </li>
          <li>No hints, and no feedback until the end.</li>
          <li>
            You test out of a lesson only if you answer <strong>all</strong> of its questions correctly.
            Choose <em>I don't know this yet</em> instead of guessing - a lucky guess would skip a lesson you
            need.
          </li>
          <li>
            Lessons you test out of still come back in your reviews, so the knowledge is checked again later.
          </li>
          <li>Nothing is saved until you finish. Leaving this page cancels the test.</li>
        </ul>
        {previous && (
          <p class="muted">
            You last took this on {formatDate(previous)}. Taking it again replaces those results.
          </p>
        )}
        <div class="row">
          <button
            type="button"
            class="button primary"
            onClick={() => {
              setAnswers([]);
              setPhase('questions');
            }}
          >
            Start the test
          </button>
          <a class="button ghost" href={lesson ? href.lesson(lesson.id) : href.home()}>
            Not now
          </a>
        </div>
      </section>
    );
  }

  if (phase === 'questions') {
    const { lesson: from, question } = items[answers.length]!;
    const onSubmit = ({ score }: SubmitArgs) => answer(score, false);
    const idPrefix = `placement-${from.id}-${question.id}`;
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>{title}</h1>
        <p class="muted">
          Question {answers.length + 1} of {items.length} · {from.title}
        </p>
        <progress max={items.length} value={answers.length} aria-label="Placement test progress" />
        <article key={idPrefix} class="exercise placement-question" aria-labelledby={`${idPrefix}-title`}>
          <h2 id={`${idPrefix}-title`} ref={questionHeading} tabIndex={-1}>
            {question.title}
          </h2>
          <Markdown source={question.prompt} class="exercise-prompt" />
          {question.type === 'mcq' && (
            <McqBody
              exercise={question}
              idPrefix={idPrefix}
              locked={false}
              submitLabel="Save and continue"
              onSubmit={onSubmit}
            />
          )}
          {question.type === 'order' && (
            <OrderBody
              exercise={question}
              locked={false}
              submitLabel="Save and continue"
              onSubmit={onSubmit}
            />
          )}
          {question.type === 'debug' && (
            <DebugBody
              exercise={question}
              locked={false}
              submitLabel="Save and continue"
              onSubmit={onSubmit}
            />
          )}
          <div class="exercise-actions">
            <button type="button" class="button ghost" onClick={() => answer(0, true)}>
              I don't know this yet
            </button>
          </div>
        </article>
      </section>
    );
  }

  return (
    <PlacementResults
      title={title}
      lessons={lessons}
      answers={answers}
      kind={kind}
      onRetake={() => setPhase('intro')}
    />
  );
}

function PlacementResults(props: {
  title: string;
  lessons: Lesson[];
  answers: Answer[];
  kind: 'path' | 'lesson';
  onRetake: () => void;
}) {
  const { title, lessons, answers, kind, onRetake } = props;
  const { state } = useProgress();
  const testedOut = lessons.filter((l) => state.placements[l.id]?.result === 'tested-out');
  const toStudy = lessons.filter((l) => state.placements[l.id]?.result !== 'tested-out');
  const first = toStudy[0];

  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>{title} - results</h1>
      <p class="lead" aria-live="polite">
        {kind === 'lesson'
          ? testedOut.length === 1
            ? 'You tested out of this lesson. You can skip it - its recall cards are now in your review queue.'
            : 'Not yet - study this lesson. The questions below show where to focus.'
          : `You tested out of ${testedOut.length} of ${lessons.length} lessons.`}
      </p>

      <ul class="placement-results">
        {lessons.map((l) => {
          const result = state.placements[l.id];
          const mine = answers.filter((a) => a.item.lesson.id === l.id);
          return (
            <li key={l.id} class="card">
              <h2>
                <a href={href.lesson(l.id)}>{l.title}</a>{' '}
                <StatusBadge status={result?.result === 'tested-out' ? 'tested-out' : 'not-started'} />
              </h2>
              <p class="small muted">
                {result ? `${result.correct} of ${result.total} correct` : ''}
                {result?.result === 'tested-out' ? ' - you can skip this lesson.' : ' - study this lesson.'}
              </p>
              <details>
                <summary>Review the questions</summary>
                {mine.map(({ item, score, dontKnow }) => (
                  <div key={item.question.id} class="placement-review">
                    <h3>
                      {item.question.title}{' '}
                      <span class={`badge ${score >= 1 ? 'status-mastered' : 'status-in-progress'}`}>
                        {dontKnow ? "Didn't know" : score >= 1 ? 'Correct' : 'Not correct'}
                      </span>
                    </h3>
                    <Markdown source={item.question.solution} />
                  </div>
                ))}
              </details>
            </li>
          );
        })}
      </ul>

      <div class="row">
        {first ? (
          <a class="button primary" href={href.lesson(first.id)}>
            {kind === 'lesson' ? 'Study this lesson' : `Start with: ${first.title}`}
          </a>
        ) : (
          <a class="button primary" href={href.review()}>
            Go to your reviews
          </a>
        )}
        <button type="button" class="button ghost" onClick={onRetake}>
          Take it again
        </button>
        <a class="button ghost" href={href.home()}>
          Home
        </a>
      </div>
      {kind === 'path' && testedOut.length > 0 && (
        <p class="small muted">
          Changed your mind about a lesson? Open it and choose <em>Study it anyway</em>. Lessons from the{' '}
          <a href={href.learn()}>curriculum</a> keep their tested-out status until you complete them.
        </p>
      )}
    </section>
  );
}
