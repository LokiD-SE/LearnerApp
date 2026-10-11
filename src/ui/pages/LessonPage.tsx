import { useEffect, useRef, useState } from 'preact/hooks';
import type { ContentIndex } from '../../content/validate';
import type { Lesson, SectionKind } from '../../content/schema';
import { useProgress } from '../../store/ProgressContext';
import { lessonProgress, lessonStatus, masteryOf } from '../../store/selectors';
import { markRead, markUnread, setNotes, toggleBookmark, visitLesson } from '../../store/state';
import { LevelBadge, MasteryBadge, StatusBadge, formatDate, percent } from '../components/Badges';
import { ExerciseCard } from '../components/ExerciseCard';
import { Markdown } from '../components/Markdown';
import { RecallCardView } from '../components/RecallCard';
import { href } from '../router';

const KIND_LABEL: Record<SectionKind, string> = {
  intuition: 'Plain language',
  what: 'What it is',
  why: 'Why it exists',
  internals: 'How it works',
  when: 'When to use',
  visual: 'Diagram',
  steps: 'Step by step',
  example: 'Real-world example',
  code: 'Code',
  'line-by-line': 'Line by line',
  tests: 'Test cases',
  mistakes: 'Mistakes and debugging',
  tradeoffs: 'Trade-offs',
  summary: 'Summary',
};

export function LessonPage({ index, id }: { index: ContentIndex; id: string }) {
  const lesson = index.lessons.get(id);
  const ref = index.refs.get(id);
  if (!ref) return <LessonNotFound id={id} />;
  if (!lesson) return <PlannedLesson index={index} id={id} />;
  return <PublishedLesson index={index} lesson={lesson} />;
}

function LessonNotFound({ id }: { id: string }) {
  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>Lesson not found</h1>
      <p>
        There is no lesson called <code>{id}</code>. It may have been renamed.
      </p>
      <p>
        <a class="button primary" href={href.learn()}>
          Browse the curriculum
        </a>
      </p>
    </section>
  );
}

function PlannedLesson({ index, id }: { index: ContentIndex; id: string }) {
  const ref = index.refs.get(id)!;
  const mod = index.modules.get(ref.moduleId);
  const subject = index.subjects.get(ref.subjectId);
  return (
    <section class="page narrow">
      <p class="crumbs">
        <a href={href.learn({ subject: ref.subjectId })}>{subject?.title}</a> / {mod?.title}
      </p>
      <h1 tabIndex={-1}>{ref.title}</h1>
      <p>
        <LevelBadge level={ref.level} /> <StatusBadge status="planned" />
      </p>
      <p>{ref.summary}</p>
      <div class="empty-state">
        <p>
          This lesson is planned but not written yet. It is on the curriculum so you can see where it fits.
        </p>
        <a class="button secondary" href={href.learn({ subject: ref.subjectId })}>
          Back to {subject?.title}
        </a>
      </div>
    </section>
  );
}

function PublishedLesson({ index, lesson }: { index: ContentIndex; lesson: Lesson }) {
  const { state, update } = useProgress();
  const ref = index.refs.get(lesson.id)!;
  const subject = index.subjects.get(ref.subjectId);
  const mod = index.modules.get(ref.moduleId);
  const progress = state.lessons[lesson.id];
  const summary = lessonProgress(index, state, lesson.id);
  const [notes, setNotesText] = useState(progress?.notes ?? '');
  const notesTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    update((s, now) => visitLesson(s, lesson.id, now));
    setNotesText(state.lessons[lesson.id]?.notes ?? '');
    window.scrollTo(0, 0);
    // Runs once per lesson opened.
  }, [lesson.id]);
  useEffect(() => () => clearTimeout(notesTimer.current), []);

  const onNotes = (value: string) => {
    setNotesText(value);
    clearTimeout(notesTimer.current);
    notesTimer.current = setTimeout(() => update((s) => setNotes(s, lesson.id, value)), 400);
  };

  const jump = (target: string) =>
    document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <article class="page lesson" aria-labelledby="lesson-title">
      <p class="crumbs">
        <a href={href.learn({ subject: ref.subjectId })}>{subject?.title}</a> / {mod?.title}
      </p>
      <header class="lesson-header">
        <h1 id="lesson-title" tabIndex={-1}>
          {lesson.title}
        </h1>
        <div class="lesson-meta">
          <LevelBadge level={lesson.level} />
          <StatusBadge status={summary.status} />
          <span class="muted">{lesson.estimatedMinutes} min</span>
          <span class="muted">
            Exercises {summary.requiredAttempted}/{summary.requiredTotal}
          </span>
          <button
            type="button"
            class={`button ghost small ${progress?.bookmarked ? 'is-on' : ''}`}
            aria-pressed={Boolean(progress?.bookmarked)}
            onClick={() => update((s) => toggleBookmark(s, lesson.id))}
          >
            {progress?.bookmarked ? '★ Bookmarked' : '☆ Bookmark'}
          </button>
        </div>
        <p class="lead">{lesson.summary}</p>
      </header>

      <div class="lesson-grid">
        <aside class="lesson-aside" aria-label="Lesson overview">
          <section class="panel">
            <h2 class="panel-title">Before you start</h2>
            {lesson.prerequisites.length === 0 ? (
              <p class="muted">No prerequisites.</p>
            ) : (
              <ul class="prereqs">
                {lesson.prerequisites.map((pid) => {
                  const pref = index.refs.get(pid)!;
                  return (
                    <li key={pid}>
                      <a href={href.lesson(pid)}>{pref.title}</a>{' '}
                      <StatusBadge status={lessonStatus(index, state, pid)} />
                    </li>
                  );
                })}
              </ul>
            )}
            <p class="muted small">
              Unsure about these? Skim them, or try this lesson's exercises first as a diagnostic.
            </p>
          </section>
          <nav class="panel toc" aria-label="Contents">
            <h2 class="panel-title">Contents</h2>
            <ol>
              <li>
                <button type="button" class="link-button" onClick={() => jump('objectives')}>
                  Objectives
                </button>
              </li>
              {lesson.sections.map((section) => (
                <li key={section.id}>
                  <button type="button" class="link-button" onClick={() => jump(`section-${section.id}`)}>
                    {section.title}
                  </button>
                </li>
              ))}
              {lesson.exercises.length > 0 && (
                <li>
                  <button type="button" class="link-button" onClick={() => jump('practice')}>
                    Practice ({lesson.exercises.length})
                  </button>
                </li>
              )}
              {lesson.recall.length > 0 && (
                <li>
                  <button type="button" class="link-button" onClick={() => jump('recall')}>
                    Test yourself
                  </button>
                </li>
              )}
            </ol>
          </nav>
          <section class="panel">
            <h2 class="panel-title">Concept mastery</h2>
            <ul class="mastery-list">
              {lesson.concepts.map((concept) => {
                const mastery = masteryOf(lesson, concept.id, state);
                return (
                  <li key={concept.id}>
                    <span>{concept.name}</span> <MasteryBadge level={mastery.level} />
                    {mastery.itemsAttempted > 0 && <span class="muted small"> {percent(mastery.score)}</span>}
                  </li>
                );
              })}
            </ul>
          </section>
        </aside>

        <div class="lesson-main">
          <section id="objectives" class="lesson-section">
            <h2>Learning objectives</h2>
            <p class="muted">By the end you should be able to:</p>
            <ul>
              {lesson.objectives.map((objective, i) => (
                <li key={i}>
                  <Markdown source={objective} inline />
                </li>
              ))}
            </ul>
            {lesson.environment && (
              <details class="environment">
                <summary>Versions, sources and assumptions</summary>
                <Markdown source={lesson.environment} />
              </details>
            )}
          </section>

          {lesson.sections.map((section) => (
            <section
              key={section.id}
              id={`section-${section.id}`}
              class={`lesson-section kind-${section.kind}`}
            >
              <p class="section-kind">{KIND_LABEL[section.kind]}</p>
              {section.collapsed ? (
                <details>
                  <summary>
                    <h2 class="inline-heading">{section.title}</h2>
                  </summary>
                  <Markdown source={section.body} />
                </details>
              ) : (
                <>
                  <h2>{section.title}</h2>
                  <Markdown source={section.body} />
                </>
              )}
            </section>
          ))}

          {lesson.exercises.length > 0 && (
            <section id="practice" class="lesson-section">
              <h2>Practice</h2>
              <p class="muted">
                Answer before you look. Hints cost a little credit; the solution unlocks after you try. Your
                first answer in each sitting is what counts towards mastery.
              </p>
              {lesson.exercises.map((exercise) => (
                <ExerciseCard key={exercise.id} lesson={lesson} exercise={exercise} mode="lesson" />
              ))}
            </section>
          )}

          {lesson.recall.length > 0 && (
            <section id="recall" class="lesson-section">
              <h2>Test yourself</h2>
              <p class="muted">
                Answer each from memory, then reveal. These cards come back in your review queue.
              </p>
              <div class="recall-grid">
                {lesson.recall.map((card) => (
                  <RecallCardView key={card.id} lesson={lesson} card={card} mode="lesson" />
                ))}
              </div>
            </section>
          )}

          <section class="lesson-section finish" aria-label="Finish the lesson">
            <h2>Finish</h2>
            {progress?.readAt ? (
              <p>
                Marked as read on {formatDate(progress.readAt)}.{' '}
                {summary.status === 'completed' || summary.status === 'mastered'
                  ? `Lesson completed${progress.completedAt ? ` on ${formatDate(progress.completedAt)}` : ''}.`
                  : `Attempt the remaining ${summary.requiredTotal - summary.requiredAttempted} required exercise(s) to complete it.`}{' '}
                <button
                  type="button"
                  class="link-button"
                  onClick={() => update((s) => markUnread(s, lesson.id))}
                >
                  Mark as unread
                </button>
              </p>
            ) : (
              <button
                type="button"
                class="button primary"
                onClick={() => update((s, now) => markRead(s, lesson, now))}
              >
                Mark as read
              </button>
            )}

            <label class="field-label" for="lesson-notes">
              My notes
            </label>
            <textarea
              id="lesson-notes"
              rows={4}
              value={notes}
              placeholder="What surprised you? What will you check in your own project?"
              onInput={(event) => onNotes((event.target as HTMLTextAreaElement).value)}
            />

            {lesson.next.length > 0 && (
              <>
                <h3>Next</h3>
                <ul>
                  {lesson.next.map((nid) => {
                    const next = index.refs.get(nid)!;
                    return (
                      <li key={nid}>
                        <a href={href.lesson(nid)}>{next.title}</a>{' '}
                        {next.planned && <StatusBadge status="planned" />}
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </section>
        </div>
      </div>
    </article>
  );
}
