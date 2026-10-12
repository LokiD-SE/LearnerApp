import { useEffect } from 'preact/hooks';
import type { ValidationResult } from '../content/validate';
import { useProgress } from '../store/ProgressContext';
import { dueReviews } from '../store/selectors';
import { HomePage } from './pages/HomePage';
import { InterviewHomePage } from './pages/InterviewHomePage';
import { InterviewPage } from './pages/InterviewPage';
import { InterviewRoundPage } from './pages/InterviewRoundPage';
import { LearnPage } from './pages/LearnPage';
import { LessonPage } from './pages/LessonPage';
import { PlacementPage } from './pages/PlacementPage';
import { PracticePage } from './pages/PracticePage';
import { ProgressPage } from './pages/ProgressPage';
import { ReviewPage } from './pages/ReviewPage';
import { SearchPage } from './pages/SearchPage';
import { href, useRoute, type Route } from './router';

export function App({ content }: { content: ValidationResult }) {
  if (!content.ok) return <ContentError errors={content.errors} />;
  return <Shell content={content} />;
}

function ContentError({ errors }: { errors: string[] }) {
  return (
    <main id="main" class="page narrow">
      <h1>The course content has errors</h1>
      <p>The app cannot start until these are fixed in the files under content/:</p>
      <ul class="error-list">
        {errors.map((error, i) => (
          <li key={i}>
            <code>{error}</code>
          </li>
        ))}
      </ul>
    </main>
  );
}

function Shell({ content }: { content: Extract<ValidationResult, { ok: true }> }) {
  const index = content.index;
  const route = useRoute();
  const { state, now, warning, dismissWarning } = useProgress();
  const due = dueReviews(index, state, now()).length;

  // Move focus to the new page's heading so keyboard and screen-reader users land on it.
  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('main h1');
    heading?.focus({ preventScroll: true });
    document.title = heading?.textContent ? `${heading.textContent} - LearnerApp` : 'LearnerApp';
  }, [route]);

  // The interview pages all live under the "Interview" link.
  const current = route.name === 'interview' || route.name === 'interview-round' ? 'interviews' : route.name;
  const navLink = (target: Route['name'], to: string, label: string, extra?: preact.ComponentChildren) => (
    <a
      href={to}
      class={`nav-link ${current === target ? 'is-active' : ''}`}
      aria-current={current === target ? 'page' : undefined}
    >
      {label}
      {extra}
    </a>
  );

  return (
    <>
      <a
        class="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById('main')?.focus();
        }}
      >
        Skip to content
      </a>
      <header class="site-header">
        <a class="brand" href={href.home()}>
          <span class="brand-mark" aria-hidden="true">
            L
          </span>{' '}
          LearnerApp
        </a>
        <nav aria-label="Main">
          {navLink('learn', href.learn(), 'Learn')}
          {navLink(
            'review',
            href.review(),
            'Review',
            due > 0 ? (
              <span class="count" aria-label={`${due} due`}>
                {due}
              </span>
            ) : null,
          )}
          {navLink('practice', href.practice(), 'Practice')}
          {navLink('interviews', href.interviews(), 'Interview')}
          {navLink('progress', href.progress(), 'Progress')}
          {navLink('search', href.search(), 'Search')}
        </nav>
      </header>
      {warning && (
        <div class="banner" role="alert">
          <p>{warning}</p>
          <button type="button" class="button ghost small" onClick={dismissWarning}>
            Dismiss
          </button>
        </div>
      )}
      <main id="main" tabIndex={-1}>
        {route.name !== 'home' && (
          <p class="back-home">
            <a class="button ghost small" href={href.home()}>
              <span aria-hidden="true">←</span> Back to home
            </a>
          </p>
        )}
        <Page route={route} index={index} />
      </main>
      <footer class="site-footer">
        <p>
          Progress is saved in this browser only. Examples use fictional systems and sandbox data - never real
          card details.
        </p>
      </footer>
    </>
  );
}

function Page({ route, index }: { route: Route; index: Extract<ValidationResult, { ok: true }>['index'] }) {
  switch (route.name) {
    case 'home':
      return <HomePage index={index} />;
    case 'learn':
      return <LearnPage index={index} subject={route.subject} stage={route.stage} />;
    case 'lesson':
      return <LessonPage key={route.id} index={index} id={route.id} focus={route.focus} />;
    case 'review':
      return <ReviewPage index={index} />;
    case 'progress':
      return <ProgressPage index={index} />;
    case 'search':
      return <SearchPage index={index} query={route.query} />;
    case 'practice':
      return <PracticePage key={route.lesson ?? 'all'} index={index} lessonId={route.lesson} />;
    case 'placement':
      return (
        <PlacementPage key={`${route.kind}/${route.id}`} index={index} kind={route.kind} id={route.id} />
      );
    case 'interviews':
      return <InterviewHomePage key={route.course ?? 'all'} index={index} course={route.course} />;
    case 'interview':
      return <InterviewPage key={route.id} index={index} id={route.id} />;
    case 'interview-round':
      return (
        <InterviewRoundPage
          key={`${route.id}/${route.round}`}
          index={index}
          id={route.id}
          round={route.round}
        />
      );
    case 'not-found':
      return (
        <section class="page narrow">
          <h1 tabIndex={-1}>Page not found</h1>
          <p>
            Nothing lives at <code>{route.path}</code>. <a href={href.home()}>Go to the home page</a>.
          </p>
        </section>
      );
  }
}
