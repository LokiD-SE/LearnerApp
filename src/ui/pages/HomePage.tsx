import type { ContentIndex } from '../../content/validate';
import { useProgress } from '../../store/ProgressContext';
import { dueReviews, lessonStatus, weakConcepts } from '../../store/selectors';
import { StatusBadge } from '../components/Badges';
import { href } from '../router';

export function HomePage({ index }: { index: ContentIndex }) {
  const { state, now } = useProgress();
  const due = dueReviews(index, state, now());
  const last = state.lastLessonId ? index.refs.get(state.lastLessonId) : undefined;
  const weak = weakConcepts(index, state).slice(0, 3);
  const published = [...index.refs.values()].filter((ref) => !ref.planned);
  const firstLesson = published[0];

  return (
    <section class="page">
      <header class="hero">
        <h1 tabIndex={-1}>Learn it, practise it, prove it.</h1>
        <p class="lead">
          Payments testing, API and mobile testing, Java and automation - taught with active recall, spaced
          repetition, worked examples and practice that has to be done, not just read.
        </p>
      </header>

      <div class="cards">
        <section class="card">
          <h2>{last ? 'Continue' : 'Start here'}</h2>
          {last ? (
            <>
              <p>
                <a href={href.lesson(last.id)}>{last.title}</a>{' '}
                <StatusBadge status={lessonStatus(index, state, last.id)} />
              </p>
              <a class="button primary" href={href.lesson(last.id)}>
                Resume lesson
              </a>
            </>
          ) : firstLesson ? (
            <>
              <p>{firstLesson.title}</p>
              <a class="button primary" href={href.lesson(firstLesson.id)}>
                Open the first lesson
              </a>
            </>
          ) : (
            <p class="muted">No lessons are published yet.</p>
          )}
        </section>

        <section class="card">
          <h2>Review</h2>
          {due.length > 0 ? (
            <>
              <p>
                <strong>{due.length}</strong> {due.length === 1 ? 'item is' : 'items are'} due. Reviewing at
                the right moment is what makes knowledge stick.
              </p>
              <a class="button primary" href={href.review()}>
                Start review
              </a>
            </>
          ) : (
            <p class="muted">Nothing due. Items you practise come back here on a spaced schedule.</p>
          )}
        </section>

        <section class="card">
          <h2>Weak areas</h2>
          {weak.length > 0 ? (
            <ul>
              {weak.map((row) => (
                <li key={row.conceptId}>
                  <a href={href.lesson(row.lesson.id)}>{row.name}</a>
                </li>
              ))}
            </ul>
          ) : (
            <p class="muted">None yet. Concepts you are still practising will show up here.</p>
          )}
        </section>
      </div>

      <section class="stages">
        <h2>The learning path</h2>
        <ol class="stage-list">
          {index.curriculum.stages.map((stage) => {
            const refs = [...index.refs.values()].filter((ref) => ref.stageId === stage.id);
            const ready = refs.filter((ref) => !ref.planned).length;
            return (
              <li key={stage.id} class="stage">
                <span class="stage-number">{stage.number}</span>
                <div>
                  <h3>{stage.title}</h3>
                  <p class="muted">{stage.summary}</p>
                  <p class="small">
                    {refs.length} lessons{ready > 0 ? `, ${ready} ready` : ', all planned'} ·{' '}
                    <a href={href.learn({ stage: stage.id })}>See lessons</a>
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </section>
    </section>
  );
}
