import type { ComponentChildren } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import { moduleTime, subjectTime } from '../../content/time';
import type { ContentIndex } from '../../content/validate';
import { useProgress } from '../../store/ProgressContext';
import { lessonStatus, LESSON_STATUS_LABEL } from '../../store/selectors';
import { href } from '../router';
import { Duration, ShortTime } from './Duration';

/** The width at which the side column sits beside the page (matches styles.css). */
const WIDE = '(min-width: 980px)';

function useMediaQuery(query: string): boolean {
  const supported = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
  const [matches, setMatches] = useState(() => supported && window.matchMedia(query).matches);
  useEffect(() => {
    if (!supported) return;
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    onChange();
    list.addEventListener('change', onChange);
    return () => list.removeEventListener('change', onChange);
  }, [query, supported]);
  return matches;
}

/**
 * Every course (subject) with its chapters (modules) and lessons, each with its study time.
 * The current course is open, the current lesson is marked, and `children` - the current
 * lesson's sections - sit under it. Open beside the page on wide screens; a collapsed panel on
 * narrow ones, so it does not push the page down.
 */
export function CourseNav({
  index,
  subject,
  lesson,
  children,
}: {
  index: ContentIndex;
  subject?: string | undefined;
  lesson?: string | undefined;
  children?: ComponentChildren;
}) {
  const { state } = useProgress();
  const wide = useMediaQuery(WIDE);
  const navRef = useRef<HTMLElement>(null);

  // Beside the page the column scrolls on its own: bring the current lesson into it.
  useEffect(() => {
    const here = navRef.current?.querySelector<HTMLElement>('.is-here');
    const column = navRef.current?.parentElement;
    if (!wide || !here || !column || column.scrollHeight <= column.clientHeight) return;
    const offset = here.getBoundingClientRect().top - column.getBoundingClientRect().top;
    if (offset < 0 || offset > column.clientHeight * 0.8)
      column.scrollTop += offset - column.clientHeight / 3;
  }, [lesson, wide]);
  return (
    <nav ref={navRef} class="panel course-nav" aria-label="Courses">
      <details open={wide}>
        <summary class="panel-title">Courses and sections</summary>
        <ul class="course-list">
          {index.curriculum.subjects.map((s) => {
            const current = s.id === subject;
            return (
              <li key={s.id} class={current ? 'is-current' : undefined}>
                <details open={current}>
                  <summary>
                    <span class="course-name">
                      <span class="course-track">{s.track}</span> {s.title}
                    </span>
                    <ShortTime total={subjectTime(index, s.id)} />
                  </summary>
                  <p class="small course-overview">
                    <a
                      href={href.learn({ subject: s.id })}
                      aria-current={current && !lesson ? 'page' : undefined}
                    >
                      Course overview
                    </a>
                  </p>
                  <ol class="chapter-list">
                    {s.modules.map((mod) => (
                      <li key={mod.id}>
                        <p class="chapter-name">
                          <span>{mod.title}</span> <ShortTime total={moduleTime(index, mod.id)} />
                        </p>
                        <ol class="outline-lessons">
                          {mod.lessons.map(({ id }) => {
                            const ref = index.refs.get(id)!;
                            const published = index.lessons.get(id);
                            const status = lessonStatus(index, state, id);
                            const done =
                              status === 'completed' || status === 'mastered' || status === 'tested-out';
                            const here = id === lesson;
                            return (
                              <li
                                key={id}
                                class={`${ref.planned ? 'is-planned' : ''} ${here ? 'is-here' : ''}`}
                              >
                                <span class="outline-row">
                                  <a href={href.lesson(id)} aria-current={here ? 'page' : undefined}>
                                    {ref.title}
                                  </a>
                                  {done && (
                                    <span class="outline-done" title={LESSON_STATUS_LABEL[status]}>
                                      <span aria-hidden="true">✓</span>
                                      <span class="sr-only">{LESSON_STATUS_LABEL[status]}</span>
                                    </span>
                                  )}
                                  {published ? (
                                    <Duration minutes={published.estimatedMinutes} />
                                  ) : (
                                    <span class="duration is-planned">planned</span>
                                  )}
                                </span>
                                {here && children}
                              </li>
                            );
                          })}
                        </ol>
                      </li>
                    ))}
                  </ol>
                </details>
              </li>
            );
          })}
        </ul>
      </details>
    </nav>
  );
}
