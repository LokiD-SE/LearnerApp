import { useState } from 'preact/hooks';
import { LEVELS, type Level } from '../../content/schema';
import { moduleTime, pathTime, stageTime, subjectTime, totalTime } from '../../content/time';
import type { ContentIndex, LessonRef } from '../../content/validate';
import { useProgress } from '../../store/ProgressContext';
import { lessonStatus, minutesLeft, type LessonStatus } from '../../store/selectors';
import { LevelBadge, StatusBadge } from '../components/Badges';
import { CourseNav } from '../components/CourseNav';
import { Duration, ShortTime, TimeSummary } from '../components/Duration';
import { href } from '../router';

type Availability = 'all' | 'ready' | 'planned';

export function LearnPage({
  index,
  subject,
  stage,
}: {
  index: ContentIndex;
  subject?: string;
  stage?: string;
}) {
  const { state } = useProgress();
  const [text, setText] = useState('');
  const [level, setLevel] = useState<Level | 'all'>('all');
  const [availability, setAvailability] = useState<Availability>('all');
  const [mine, setMine] = useState<LessonStatus | 'all'>('all');

  const subjectInfo = subject ? index.subjects.get(subject) : undefined;
  const stageInfo = stage ? index.curriculum.stages.find((s) => s.id === stage) : undefined;
  const needle = text.trim().toLowerCase();

  const matches = (ref: LessonRef) => {
    if (subject && ref.subjectId !== subject) return false;
    if (stage && ref.stageId !== stage) return false;
    if (level !== 'all' && ref.level !== level) return false;
    if (availability === 'ready' && ref.planned) return false;
    if (availability === 'planned' && !ref.planned) return false;
    if (mine !== 'all' && lessonStatus(index, state, ref.id) !== mine) return false;
    if (needle && !`${ref.title} ${ref.summary}`.toLowerCase().includes(needle)) return false;
    return true;
  };

  const shown = [...index.refs.values()].filter(matches);
  // The time of what the heading names: the course, the stage or the whole curriculum.
  const scope = [...index.refs.values()].filter(
    (ref) => (!subject || ref.subjectId === subject) && (!stage || ref.stageId === stage),
  );
  const scopeTime = subjectInfo
    ? subjectTime(index, subjectInfo.id)
    : stageInfo
      ? stageTime(index, stageInfo.id)
      : totalTime(index, scope);
  const filtersActive = Boolean(needle) || level !== 'all' || availability !== 'all' || mine !== 'all';

  return (
    <section class="page">
      <h1 tabIndex={-1}>
        {subjectInfo
          ? subjectInfo.title
          : stageInfo
            ? `Stage ${stageInfo.number}: ${stageInfo.title}`
            : 'Curriculum'}
      </h1>
      <p class="lead">
        {subjectInfo?.summary ??
          stageInfo?.summary ??
          'Seven stages, from foundations to interview simulations. Planned lessons are listed so you can see where everything fits.'}
      </p>
      <TimeSummary total={scopeTime} left={minutesLeft(index, state, scope)} />
      {(subject || stage) && (
        <p>
          <a href={href.learn()}>Show the whole curriculum</a>
        </p>
      )}

      <div class="course-layout">
        <aside class="course-aside" aria-label="Course outline">
          <CourseNav index={index} subject={subjectInfo?.id} />
        </aside>
        <div class="course-main">
          <form class="filters" role="search" onSubmit={(e) => e.preventDefault()}>
            <label>
              <span>Filter</span>
              <input
                type="search"
                value={text}
                placeholder="Title or topic"
                onInput={(e) => setText((e.target as HTMLInputElement).value)}
              />
            </label>
            <label>
              <span>Level</span>
              <select
                value={level}
                onChange={(e) => setLevel((e.target as HTMLSelectElement).value as Level | 'all')}
              >
                <option value="all">All levels</option>
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Lessons</span>
              <select
                value={availability}
                onChange={(e) => setAvailability((e.target as HTMLSelectElement).value as Availability)}
              >
                <option value="all">Ready and planned</option>
                <option value="ready">Ready to study</option>
                <option value="planned">Planned</option>
              </select>
            </label>
            <label>
              <span>My progress</span>
              <select
                value={mine}
                onChange={(e) => setMine((e.target as HTMLSelectElement).value as LessonStatus | 'all')}
              >
                <option value="all">Any</option>
                <option value="not-started">Not started</option>
                <option value="in-progress">In progress</option>
                <option value="tested-out">Tested out</option>
                <option value="completed">Completed</option>
                <option value="mastered">Mastered</option>
              </select>
            </label>
          </form>

          <p class="muted" aria-live="polite">
            {shown.length} {shown.length === 1 ? 'lesson' : 'lessons'}
            {filtersActive ? ' match your filters' : ''}.
          </p>

          {shown.length === 0 ? (
            <div class="empty-state">
              <p>No lessons match. Try clearing a filter.</p>
              <button
                type="button"
                class="button secondary"
                onClick={() => {
                  setText('');
                  setLevel('all');
                  setAvailability('all');
                  setMine('all');
                }}
              >
                Clear filters
              </button>
            </div>
          ) : (
            index.curriculum.stages.map((s) => {
              const inStage = shown.filter((ref) => ref.stageId === s.id);
              if (inStage.length === 0) return null;
              const moduleIds = [...new Set(inStage.map((ref) => ref.moduleId))];
              return (
                <section key={s.id} class="stage-block" aria-labelledby={`stage-${s.id}`}>
                  <h2 id={`stage-${s.id}`}>
                    <span class="stage-number">{s.number}</span> {s.title}
                    {!subject && <ShortTime total={stageTime(index, s.id)} />}
                  </h2>
                  {moduleIds.map((moduleId) => {
                    const mod = index.modules.get(moduleId)!;
                    const subj = index.subjects.get(mod.subjectId)!;
                    return (
                      <div key={moduleId} class="module">
                        <h3>
                          {mod.title} <ShortTime total={moduleTime(index, moduleId)} />{' '}
                          <span class="muted small">
                            · {subj.track}: {subj.title}
                          </span>
                        </h3>
                        <ul class="lesson-list">
                          {inStage
                            .filter((ref) => ref.moduleId === moduleId)
                            .map((ref) => (
                              <li key={ref.id} class={ref.planned ? 'is-planned' : ''}>
                                <a href={href.lesson(ref.id)}>{ref.title}</a>
                                <span class="lesson-badges">
                                  {!ref.planned && (
                                    <Duration minutes={index.lessons.get(ref.id)!.estimatedMinutes} />
                                  )}
                                  <LevelBadge level={ref.level} />
                                  <StatusBadge status={lessonStatus(index, state, ref.id)} />
                                </span>
                                {ref.summary && <p class="muted small">{ref.summary}</p>}
                              </li>
                            ))}
                        </ul>
                      </div>
                    );
                  })}
                </section>
              );
            })
          )}

          {index.curriculum.paths.length > 0 && !subject && !stage && (
            <section class="paths">
              <h2>Learning paths</h2>
              <div class="cards">
                {index.curriculum.paths.map((path) => {
                  const ready = path.lessons.filter((id) => !index.refs.get(id)?.planned).length;
                  return (
                    <div key={path.id} class="card">
                      <h3>{path.title}</h3>
                      <p>
                        <LevelBadge level={path.level} />{' '}
                        <span class="muted small">
                          {path.lessons.length} lessons, {ready} ready
                        </span>
                      </p>
                      <TimeSummary total={pathTime(index, path.lessons)} />
                      <p class="muted">{path.summary}</p>
                      <ol class="small">
                        {path.lessons.map((id) => (
                          <li key={id}>
                            <a href={href.lesson(id)}>{index.refs.get(id)?.title}</a>
                          </li>
                        ))}
                      </ol>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
