import { pathTime, stageTime } from '../../content/time';
import type { ContentIndex } from '../../content/validate';
import { useProfiles } from '../../store/ProfilesContext';
import { useProgress } from '../../store/ProgressContext';
import {
  dueReviews,
  lessonStatus,
  minutesLeft,
  pathProgress,
  placementItems,
  weakConcepts,
} from '../../store/selectors';
import { StatusBadge } from '../components/Badges';
import { ShortTime, TimeSummary } from '../components/Duration';
import { href } from '../router';

export function HomePage({ index }: { index: ContentIndex }) {
  const { state, now } = useProgress();
  const profiles = useProfiles().state;
  const profile = profiles.activeUserId ? profiles.profiles[profiles.activeUserId] : undefined;
  const due = dueReviews(index, state, now());
  const last = state.lastLessonId ? index.refs.get(state.lastLessonId) : undefined;
  const weak = weakConcepts(index, state).slice(0, 3);
  const lastStatus = last ? lessonStatus(index, state, last.id) : undefined;
  const resume = last && lastStatus !== 'completed' && lastStatus !== 'mastered' ? last : undefined;
  const mainPath = index.curriculum.paths[0];
  const mainProgress = mainPath ? pathProgress(index, state, mainPath) : undefined;
  // Without a path, fall back to the first published lesson in curriculum order.
  const nextLesson = mainProgress?.next ?? [...index.refs.values()].find((ref) => !ref.planned);
  const fresh = state.attempts.length === 0 && !last && Object.keys(state.placements).length === 0;
  const placementCount = mainPath ? placementItems(index, { kind: 'path', id: mainPath.id }).length : 0;
  const offerPlacement =
    Boolean(mainPath) && placementCount > 0 && Object.keys(state.placements).length === 0;

  return (
    <section class="page">
      <header class="hero">
        <h1 tabIndex={-1}>Learn it, practise it, prove it.</h1>
        <p class="lead">
          Payments testing, API and mobile testing, Java and automation - taught with active recall, spaced
          repetition, worked examples and practice that has to be done, not just read.
        </p>
      </header>

      {profile && (
        <section class="card welcome" aria-labelledby="welcome-title">
          <h2 id="welcome-title">
            {fresh ? `Welcome, ${profile.firstName}` : `Welcome back, ${profile.firstName}`}
          </h2>
          <p>
            <strong>{profile.completedLessons.length}</strong> of {index.lessons.size} lessons completed (
            {profile.progressPercentage}%)
          </p>
          <progress
            max={100}
            value={profile.progressPercentage}
            aria-label={`Overall progress: ${profile.progressPercentage}%`}
          />
          <p class="small">
            <a href={href.progress()}>See your activity</a>
          </p>
        </section>
      )}

      <div class="cards">
        <section class="card">
          <h2>{resume ? 'Continue' : fresh ? 'Start here' : 'Next on your path'}</h2>
          {resume ? (
            <>
              <p>
                <a href={href.lesson(resume.id)}>{resume.title}</a> <StatusBadge status={lastStatus!} />
              </p>
              <a class="button primary" href={href.lesson(resume.id)}>
                Resume study
              </a>
            </>
          ) : nextLesson ? (
            <>
              <p>
                {mainPath && mainProgress?.next ? <span class="muted small">{mainPath.title} · </span> : null}
                {nextLesson.title}
              </p>
              <a class="button primary" href={href.lesson(nextLesson.id)}>
                {fresh ? 'Open the first lesson' : 'Open the next lesson'}
              </a>
            </>
          ) : (
            <p class="muted">
              {index.lessons.size > 0
                ? 'You have completed every published lesson on your path. New lessons will appear here.'
                : 'No lessons are published yet.'}
            </p>
          )}
        </section>

        {offerPlacement && mainPath && (
          <section class="card">
            <h2>Already know some of this?</h2>
            <p>
              Take the placement test for {mainPath.title}: {placementCount} questions, about{' '}
              {Math.ceil(placementCount * 1.5)} minutes. Skip the lessons you can show you know.
            </p>
            <a class="button secondary" href={href.placement('path', mainPath.id)}>
              Take the placement test
            </a>
          </section>
        )}

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
            <>
              <ul>
                {weak.map((row) => (
                  <li key={row.conceptId}>
                    <a href={href.lesson(row.lesson.id)}>{row.name}</a>
                  </li>
                ))}
              </ul>
              <a class="button secondary" href={href.practice()}>
                Practise weak areas
              </a>
            </>
          ) : (
            <p class="muted">None yet. Concepts you are still practising will show up here.</p>
          )}
        </section>
      </div>

      {index.curriculum.paths.length > 0 && (
        <section class="paths" aria-labelledby="paths-title">
          <h2 id="paths-title">Learning paths</h2>
          <ul class="path-list">
            {index.curriculum.paths.map((path) => {
              const progress = pathProgress(index, state, path);
              const refs = path.lessons.flatMap((id) => index.refs.get(id) ?? []);
              return (
                <li key={path.id} class="card">
                  <h3>{path.title}</h3>
                  <p class="small muted">
                    {progress.ready === 0
                      ? `${progress.total} lessons, all planned`
                      : `${progress.completed} completed` +
                        (progress.testedOut ? `, ${progress.testedOut} tested out` : '') +
                        ` of ${progress.ready} ready lessons` +
                        (progress.ready < progress.total
                          ? ` (${progress.total - progress.ready} more planned)`
                          : '')}
                  </p>
                  <TimeSummary total={pathTime(index, path.lessons)} left={minutesLeft(index, state, refs)} />
                  <progress
                    max={Math.max(progress.ready, 1)}
                    value={progress.completed + progress.testedOut}
                    aria-label={`${path.title}: ${progress.completed + progress.testedOut} of ${progress.ready} done`}
                  />
                  {progress.next ? (
                    <p class="small">
                      Next: <a href={href.lesson(progress.next.id)}>{progress.next.title}</a>
                    </p>
                  ) : (
                    <p class="small muted">
                      {progress.ready > 0 ? 'All ready lessons completed.' : 'Lessons coming soon.'}
                    </p>
                  )}
                  {progress.ready > 0 && (
                    <p class="small">
                      <a href={href.interviews(`path:${path.id}`)}>Practise an interview for this path</a>
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section class="stages">
        <h2>The stages</h2>
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
                    <ShortTime total={stageTime(index, stage.id)} /> ·{' '}
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
