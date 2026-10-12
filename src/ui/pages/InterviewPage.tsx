/**
 * One practice interview: its rounds, where the latest attempt is, overall feedback, and how
 * every attempt went round by round - so retakes show progress.
 */
import { useState } from 'preact/hooks';
import type { ContentIndex } from '../../content/validate';
import {
  attemptSummaries,
  courseKey,
  courseOf,
  nextRound,
  roundReport,
  type FocusArea,
  type RoundResult,
} from '../../store/interviews';
import { useProgress } from '../../store/ProgressContext';
import { deleteInterview, startInterviewAttempt, type MockInterview } from '../../store/state';
import { formatDate, percent } from '../components/Badges';
import { Markdown } from '../components/Markdown';
import { href } from '../router';
import { ProfileDetails } from './InterviewHomePage';

export function InterviewNotFound({ id }: { id: string }) {
  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>Interview not found</h1>
      <p>
        There is no saved interview <code>{id}</code> in this browser.{' '}
        <a href={href.interviews()}>Generate an interview</a>.
      </p>
    </section>
  );
}

export const interviewName = (index: ContentIndex, interview: MockInterview) =>
  `${index.interviews?.profiles.find((p) => p.id === interview.profileId)?.name ?? 'Practice'} interview`;

export function BandBadge({ result }: { result: RoundResult }) {
  return <span class={`badge band-${result.band.id}`}>{result.band.label}</span>;
}

export function InterviewPage({ index, id }: { index: ContentIndex; id: string }) {
  const { state, update } = useProgress();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const interview = state.interviews.find((candidate) => candidate.id === id);
  const content = index.interviews;
  if (!interview || !content) return <InterviewNotFound id={id} />;

  const profile = content.profiles.find((p) => p.id === interview.profileId);
  const course = courseOf(index, interview.course);
  const summaries = attemptSummaries(index, interview);
  const latest = summaries.at(-1);
  const next = nextRound(interview);
  const inProgress = latest !== undefined && next !== undefined;

  const startAttempt = () => {
    update((s, now) => startInterviewAttempt(s, interview.id, now));
    window.location.hash = href.interviewRound(interview.id, 0);
  };

  // Overall feedback from the latest attempt's finished rounds.
  const finished = latest
    ? interview.rounds.flatMap((_, r) => {
        const report = latest.rounds[r]?.finished
          ? roundReport(index, interview, latest.attempt - 1, r)
          : undefined;
        return report ? [{ round: r, report }] : [];
      })
    : [];
  const focusAreas: FocusArea[] = [];
  for (const { report } of finished) {
    for (const area of report.focusAreas) {
      const existing = focusAreas.find((a) => a.name === area.name);
      if (existing) existing.questions.push(...area.questions);
      else focusAreas.push({ ...area, questions: [...area.questions] });
    }
  }
  focusAreas.sort((a, b) => b.questions.length - a.questions.length);
  const ranked = [...finished].sort((a, b) => b.report.result.score - a.report.result.score);

  return (
    <section class="page narrow">
      <p class="crumbs">
        <a href={href.interviews()}>Interview practice</a>
      </p>
      <h1 tabIndex={-1}>{interviewName(index, interview)}</h1>
      <p class="lead">
        For <strong>{course?.title ?? courseKey(interview.course)}</strong> · {interview.rounds.length} rounds
        · generated {formatDate(interview.createdAt)}
      </p>

      {profile && (
        <details class="panel company-loop">
          <summary>How {profile.name} is reported to interview, and the sources</summary>
          <ProfileDetails profile={profile} content={content} />
        </details>
      )}

      <div class="row interview-actions">
        {!latest && (
          <button type="button" class="button primary" onClick={startAttempt}>
            Start the interview
          </button>
        )}
        {inProgress && (
          <a class="button primary" href={href.interviewRound(interview.id, next)}>
            Continue: round {next + 1}
          </a>
        )}
        {latest && (
          <button type="button" class={`button ${inProgress ? 'ghost' : 'primary'}`} onClick={startAttempt}>
            {inProgress ? 'Start a new attempt' : 'Retake the interview'}
          </button>
        )}
      </div>

      <h2>Rounds</h2>
      <ol class="interview-rounds">
        {interview.rounds.map((round, r) => {
          const type = content.roundTypes.get(round.type);
          const result = latest?.rounds[r];
          return (
            <li key={r} class="card">
              <h3>
                <a href={href.interviewRound(interview.id, r)}>
                  Round {r + 1}: {round.label}
                </a>
              </h3>
              <p class="small muted">
                {type?.title ?? round.type} · {round.questions.length}{' '}
                {round.questions.length === 1 ? 'question' : 'questions'} · real round about{' '}
                {type?.minutes ?? '?'} min
              </p>
              {type && <p class="small">{type.summary}</p>}
              <p class="small">
                {!result ? (
                  latest ? (
                    'Not started in this attempt.'
                  ) : (
                    'Not started.'
                  )
                ) : result.finished ? (
                  <>
                    Latest: <strong>{percent(result.score)}</strong> <BandBadge result={result} />
                  </>
                ) : (
                  `In progress - ${result.answered} of ${result.total} answered.`
                )}
              </p>
            </li>
          );
        })}
      </ol>

      {finished.length > 0 && latest && (
        <section aria-labelledby="overall-feedback" class="panel">
          <h2 id="overall-feedback">
            {latest.complete ? 'Overall feedback' : 'Feedback so far'} - attempt {latest.attempt}
          </h2>
          <div class="stats">
            <div class="stat">
              <span class="muted small">Average of finished rounds</span>
              <span class="stat-value">{percent(latest.overall ?? 0)}</span>
            </div>
            <div class="stat">
              <span class="muted small">Rounds finished</span>
              <span class="stat-value">
                {finished.length}/{interview.rounds.length}
              </span>
            </div>
          </div>
          {ranked.length > 1 && (
            <p>
              Strongest: <strong>round {ranked[0]!.round + 1}</strong> (
              {percent(ranked[0]!.report.result.score)}). Weakest:{' '}
              <strong>round {ranked.at(-1)!.round + 1}</strong> ({percent(ranked.at(-1)!.report.result.score)}
              ).
            </p>
          )}
          {focusAreas.length > 0 ? (
            <>
              <h3>Focus next on</h3>
              <ul class="focus-areas">
                {focusAreas.slice(0, 5).map((area) => (
                  <li key={area.name}>
                    <strong>{area.name}</strong>
                    {area.href && (
                      <>
                        {' '}
                        - <a href={area.href}>study it</a>
                      </>
                    )}
                    {area.improve && <Markdown source={area.improve} class="small" />}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p>Every finished question was answered well. Retake later to check it sticks.</p>
          )}
        </section>
      )}

      {summaries.length > 0 && (
        <section aria-labelledby="attempt-history">
          <h2 id="attempt-history">Your attempts, round by round</h2>
          <div class="table-scroll" tabIndex={0}>
            <table>
              <caption class="sr-only">Score per round in each attempt</caption>
              <thead>
                <tr>
                  <th scope="col">Round</th>
                  {summaries.map((s) => (
                    <th key={s.attempt} scope="col">
                      Attempt {s.attempt}
                      <span class="small muted block">{formatDate(s.startedAt)}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {interview.rounds.map((round, r) => (
                  <tr key={r}>
                    <th scope="row">
                      {r + 1}. {round.label}
                    </th>
                    {summaries.map((s, a) => {
                      const result = s.rounds[r];
                      const before = summaries
                        .slice(0, a)
                        .map((earlier) => earlier.rounds[r])
                        .filter((earlier) => earlier?.finished)
                        .at(-1);
                      const change =
                        result?.finished && before
                          ? Math.round((result.score - before.score) * 100)
                          : undefined;
                      return (
                        <td key={s.attempt}>
                          {!result ? (
                            <span class="muted">-</span>
                          ) : result.finished ? (
                            <>
                              {percent(result.score)} <BandBadge result={result} />
                              {change !== undefined && change !== 0 && (
                                <span class={`small ${change > 0 ? 'trend-up' : 'trend-down'}`}>
                                  {' '}
                                  {change > 0 ? `▲ +${change}` : `▼ ${change}`}
                                </span>
                              )}
                            </>
                          ) : (
                            <span class="muted">in progress</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr>
                  <th scope="row">Average of finished rounds</th>
                  {summaries.map((s) => (
                    <td key={s.attempt}>
                      <strong>{s.overall === undefined ? '-' : percent(s.overall)}</strong>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div class="row interview-actions">
        <a class="button ghost" href={href.interviews(courseKey(interview.course))}>
          Generate a new interview for this course
        </a>
        {!confirmDelete ? (
          <button type="button" class="button ghost" onClick={() => setConfirmDelete(true)}>
            Delete this interview
          </button>
        ) : (
          <div class="confirm" role="group" aria-label="Confirm delete">
            <p>Delete this interview and all its attempts? This cannot be undone.</p>
            <div class="row">
              <button
                type="button"
                class="button primary"
                onClick={() => {
                  update((s) => deleteInterview(s, interview.id));
                  window.location.hash = href.interviews();
                }}
              >
                Delete
              </button>
              <button type="button" class="button ghost" onClick={() => setConfirmDelete(false)}>
                Keep it
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
