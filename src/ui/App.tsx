import { useEffect } from 'preact/hooks';
import type { ValidationResult } from '../content/validate';
import { useProgress } from '../store/ProgressContext';
import { dueReviews } from '../store/selectors';
import { HomePage } from './pages/HomePage';
import { LearnPage } from './pages/LearnPage';
import { LessonPage } from './pages/LessonPage';
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

  const current = route.name;
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
      return <LessonPage key={route.id} index={index} id={route.id} />;
    case 'review':
      return <ReviewPage index={index} />;
    case 'progress':
      return <ProgressPage index={index} />;
    case 'search':
      return <SearchPage index={index} query={route.query} />;
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
