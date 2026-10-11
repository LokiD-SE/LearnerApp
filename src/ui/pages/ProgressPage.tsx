import { useState } from 'preact/hooks';
import type { ContentIndex } from '../../content/validate';
import { MASTERY_LEVELS } from '../../domain/mastery';
import { useProgress } from '../../store/ProgressContext';
import { conceptRows, lessonStatus, weakConcepts } from '../../store/selectors';
import type { ProgressState } from '../../store/state';
import { exportProgress, parseProgress } from '../../store/storage';
import { MasteryBadge, StatusBadge, formatDate, percent } from '../components/Badges';
import { href } from '../router';

export function ProgressPage({ index }: { index: ContentIndex }) {
  const { state, replace } = useProgress();
  const rows = conceptRows(index, state);
  const weak = weakConcepts(index, state);
  const published = [...index.lessons.keys()];
  const completed = published.filter((id) =>
    ['completed', 'mastered'].includes(lessonStatus(index, state, id)),
  ).length;
  const bookmarks = Object.entries(state.lessons).filter(([id, l]) => l.bookmarked && index.refs.has(id));
  const recent = [...state.attempts].reverse().slice(0, 15);
  const placements = Object.entries(state.placements).filter(([id]) => index.refs.has(id));
  const [pending, setPending] = useState<ProgressState | undefined>();
  const [importError, setImportError] = useState<string | undefined>();
  const [importDone, setImportDone] = useState(false);

  const download = () => {
    const blob = new Blob([exportProgress(state)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `learnerapp-progress-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const readFile = async (file: File | undefined) => {
    setImportError(undefined);
    setImportDone(false);
    if (!file) return;
    const parsed = parseProgress(await file.text());
    if (parsed.ok) setPending(parsed.state);
    else setImportError(`That file could not be imported: ${parsed.error}.`);
  };

  return (
    <section class="page">
      <h1 tabIndex={-1}>Progress</h1>

      <div class="stats">
        <div class="stat">
          <span class="stat-value">
            {completed}/{published.length}
          </span>
          <span class="stat-label">lessons completed</span>
        </div>
        {MASTERY_LEVELS.filter((level) => level !== 'not-started').map((level) => (
          <div class="stat" key={level}>
            <span class="stat-value">{rows.filter((r) => r.mastery.level === level).length}</span>
            <span class="stat-label">
              <MasteryBadge level={level} />
            </span>
          </div>
        ))}
      </div>
      <p class="muted small">
        Attempted = some evidence. Practising = scoring 60%+. Proficient = 80%+ with most items covered and a
        practical exercise passed. Mastered = proficient and recalled again in a review at least a day later.
      </p>

      <section>
        <h2>Weak areas</h2>
        {weak.length === 0 ? (
          <p class="muted">Nothing flagged. Concepts you have attempted but not yet secured appear here.</p>
        ) : (
          <ul>
            {weak.map((row) => (
              <li key={row.conceptId}>
                <a href={href.lesson(row.lesson.id)}>{row.name}</a> <MasteryBadge level={row.mastery.level} />{' '}
                <span class="muted small">{percent(row.mastery.score)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Placement results</h2>
        {placements.length === 0 ? (
          <p class="muted">
            No placement tests taken. Lessons with placement questions offer <em>Test out</em> in their
            "Before you start" panel.
          </p>
        ) : (
          <ul>
            {placements.map(([id, result]) => (
              <li key={id}>
                <a href={href.lesson(id)}>{index.refs.get(id)!.title}</a>{' '}
                <StatusBadge status={result.result === 'tested-out' ? 'tested-out' : 'not-started'} />{' '}
                <span class="muted small">
                  {result.correct} of {result.total} correct on {formatDate(result.at)}
                  {result.result === 'study' ? ' - study recommended' : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Concepts</h2>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Concept</th>
                <th>Lesson</th>
                <th>Level</th>
                <th>Score</th>
                <th>Coverage</th>
                <th>Practical</th>
                <th>Retained</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.conceptId}>
                  <td>{row.name}</td>
                  <td>
                    <a href={href.lesson(row.lesson.id)}>{row.lesson.title}</a>
                  </td>
                  <td>
                    <MasteryBadge level={row.mastery.level} />
                  </td>
                  <td>{row.mastery.itemsAttempted ? percent(row.mastery.score) : '-'}</td>
                  <td>
                    {row.mastery.itemsAttempted}/{row.mastery.itemsTotal}
                  </td>
                  <td>{row.mastery.practical ? 'Yes' : 'Not yet'}</td>
                  <td>{row.mastery.retained ? 'Yes' : 'Not yet'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Bookmarks</h2>
        {bookmarks.length === 0 ? (
          <p class="muted">No bookmarks. Use ☆ Bookmark on a lesson to keep it handy.</p>
        ) : (
          <ul>
            {bookmarks.map(([id]) => (
              <li key={id}>
                <a href={href.lesson(id)}>{index.refs.get(id)!.title}</a>{' '}
                <StatusBadge status={lessonStatus(index, state, id)} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Recent activity</h2>
        {recent.length === 0 ? (
          <p class="muted">No attempts yet.</p>
        ) : (
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Item</th>
                  <th>Credit</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((attempt, i) => {
                  const lesson = index.lessons.get(attempt.lessonId);
                  const title =
                    attempt.kind === 'exercise'
                      ? lesson?.exercises.find((e) => e.id === attempt.itemId)?.title
                      : lesson?.recall.find((c) => c.id === attempt.itemId)?.prompt;
                  return (
                    <tr key={i}>
                      <td>{formatDate(attempt.at)}</td>
                      <td>{title ?? attempt.itemId}</td>
                      <td>{percent(attempt.credit)}</td>
                      <td class="small">
                        {[
                          attempt.mode === 'review' ? 'review' : 'lesson',
                          attempt.firstTry ? 'first try' : 'retry',
                          attempt.selfAssessed ? 'self-assessed' : 'auto-graded',
                          attempt.hintsUsed ? `${attempt.hintsUsed} hint(s)` : '',
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2>Back up or move your progress</h2>
        <p class="muted">
          Progress is stored only in this browser. Export it to keep a copy or to continue on another device.
        </p>
        <div class="row">
          <button type="button" class="button secondary" onClick={download}>
            Export progress
          </button>
          <label class="button secondary file-button">
            Import progress
            <input
              type="file"
              accept="application/json,.json"
              onChange={(e) => void readFile((e.target as HTMLInputElement).files?.[0])}
            />
          </label>
        </div>
        {importError && (
          <p class="error" role="alert">
            {importError}
          </p>
        )}
        {pending && (
          <div class="confirm" role="alert">
            <p>
              Replace your current progress with the imported file ({pending.attempts.length} attempts,{' '}
              {Object.keys(pending.lessons).length} lessons)? This cannot be undone - export first if unsure.
            </p>
            <button
              type="button"
              class="button primary"
              onClick={() => {
                replace(pending);
                setPending(undefined);
                setImportDone(true);
              }}
            >
              Replace my progress
            </button>{' '}
            <button type="button" class="button ghost" onClick={() => setPending(undefined)}>
              Cancel
            </button>
          </div>
        )}
        {importDone && <p role="status">Progress imported.</p>}
      </section>
    </section>
  );
}
