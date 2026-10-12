/**
 * One round of a practice interview, in the latest attempt: what the round assesses, then its
 * questions against the clock, then a report - score, what went well, what to improve, and how
 * this attempt compares with earlier ones at the same round.
 */
import type { RefObject } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import type { RoundType } from '../../content/schema';
import type { ContentIndex } from '../../content/validate';
import { resolveQuestion, roundReport, type RoundReport } from '../../store/interviews';
import { useProgress } from '../../store/ProgressContext';
import {
  finishInterviewRound,
  startInterviewAttempt,
  startInterviewRound,
  type MockInterview,
} from '../../store/state';
import { percent } from '../components/Badges';
import { InterviewQuestion } from '../components/InterviewQuestion';
import { Markdown } from '../components/Markdown';
import { href } from '../router';
import { BandBadge, InterviewNotFound, interviewName } from './InterviewPage';

export function InterviewRoundPage({ index, id, round }: { index: ContentIndex; id: string; round: number }) {
  const { state, update } = useProgress();
  const reportHeading = useRef<HTMLHeadingElement>(null);
  const [justFinished, setJustFinished] = useState(false);
  const interview = state.interviews.find((candidate) => candidate.id === id);
  const definition = interview?.rounds[round];
  const roundType = definition && index.interviews?.roundTypes.get(definition.type);

  useEffect(() => {
    if (justFinished) {
      reportHeading.current?.focus();
      reportHeading.current?.scrollIntoView({ block: 'start' });
    }
  }, [justFinished]);

  if (!interview || !definition || !roundType) return <InterviewNotFound id={id} />;

  const attemptIndex = interview.attempts.length - 1;
  const record = interview.attempts[attemptIndex]?.rounds[String(round)];
  const questions = definition.questions.flatMap((key) => {
    const question = resolveQuestion(index, key);
    return question ? [question] : [];
  });
  const missing = definition.questions.length - questions.length;
  const isLast = round === interview.rounds.length - 1;

  const header = (
    <>
      <p class="crumbs">
        <a href={href.interviews()}>Interview practice</a> ›{' '}
        <a href={href.interview(interview.id)}>{interviewName(index, interview)}</a>
      </p>
      <h1 tabIndex={-1}>
        Round {round + 1} of {interview.rounds.length}: {definition.label}
      </h1>
      <p class="lead">
        {roundType.title} · {questions.length} {questions.length === 1 ? 'question' : 'questions'} · the real
        round is usually about {roundType.minutes} minutes
        {interview.attempts.length > 1 ? ` · attempt ${interview.attempts.length}` : ''}
      </p>
    </>
  );

  if (!record) {
    return (
      <section class="page narrow">
        {header}
        <p>{roundType.summary}</p>
        <RoundBrief roundType={roundType} />
        <ul class="placement-rules">
          <li>Answer each question before you look at the model answer - write spoken answers down.</li>
          <li>
            Hints are there if you're stuck; each one costs 15% of that question's credit, like a nudge from
            the interviewer.
          </li>
          <li>Self-assessed answers are only as useful as your honesty when ticking the rubric.</li>
          <li>Finish the round to get your report. Unanswered questions score zero.</li>
        </ul>
        <div class="row">
          <button
            type="button"
            class="button primary"
            onClick={() => update((s, now) => startInterviewRound(s, interview.id, round, now))}
          >
            Start round {round + 1}
          </button>
          <a class="button ghost" href={href.interview(interview.id)}>
            Back to the interview
          </a>
        </div>
      </section>
    );
  }

  const finished = Boolean(record.finishedAt);
  const answered = questions.filter((q) => record.answers[q.key]).length;
  const report = finished ? roundReport(index, interview, attemptIndex, round) : undefined;

  return (
    <section class="page narrow">
      {header}
      {!finished && <RoundTimer startedAt={record.startedAt} minutes={roundType.minutes} />}
      {finished && report && (
        <RoundReportView
          report={report}
          roundType={roundType}
          interview={interview}
          round={round}
          headingRef={reportHeading}
        />
      )}
      {missing > 0 && (
        <p class="small muted">
          {missing} {missing === 1 ? 'question' : 'questions'} from this interview no longer exist in the
          course content and {missing === 1 ? 'was' : 'were'} left out.
        </p>
      )}

      {finished && <h2>Your answers and the model answers</h2>}
      {!finished && (
        <details class="panel">
          <summary>What this round assesses</summary>
          <RoundBrief roundType={roundType} />
        </details>
      )}
      {questions.map((question, i) => (
        <InterviewQuestion
          key={`${attemptIndex}-${question.key}`}
          interviewId={interview.id}
          roundIndex={round}
          question={question}
          number={i + 1}
          total={questions.length}
          record={record}
          practice={index.curriculum.practice}
        />
      ))}

      {!finished ? (
        <div class="panel finish-round">
          <p>
            {answered} of {questions.length} answered.
            {answered < questions.length && ' Questions you leave unanswered score zero.'}
          </p>
          <button
            type="button"
            class="button primary"
            onClick={() => {
              update((s, now) => finishInterviewRound(s, interview.id, round, now));
              setJustFinished(true);
            }}
          >
            Finish round and see my report
          </button>
        </div>
      ) : (
        <RoundNavigation interview={interview} round={round} isLast={isLast} />
      )}
    </section>
  );
}

function RoundBrief({ roundType }: { roundType: RoundType }) {
  return (
    <div class="round-brief">
      <h3>What the interviewer looks for</h3>
      <ul>
        {roundType.assesses.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
      <h3>Tips</h3>
      <ul>
        {roundType.tips.map((tip, i) => (
          <li key={i}>{tip}</li>
        ))}
      </ul>
    </div>
  );
}

const clock = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

function RoundTimer({ startedAt, minutes }: { startedAt: string; minutes: number }) {
  const { now } = useProgress();
  const [elapsed, setElapsed] = useState(() => now().getTime() - Date.parse(startedAt));
  useEffect(() => {
    const timer = setInterval(() => setElapsed(now().getTime() - Date.parse(startedAt)), 1000);
    return () => clearInterval(timer);
  }, [startedAt, now]);
  const over = elapsed > minutes * 60000;
  return (
    <p class={`round-timer ${over ? 'is-over' : ''}`}>
      <span aria-hidden="true">⏱ {clock(elapsed)}</span>
      <span class="sr-only">Timer running.</span> <span class="muted small">of about {minutes}:00</span>
      {over && <span class="small"> - over the usual time; finish when you're ready.</span>}
    </p>
  );
}

function RoundReportView(props: {
  report: RoundReport;
  roundType: RoundType;
  interview: MockInterview;
  round: number;
  headingRef: RefObject<HTMLHeadingElement>;
}) {
  const { report, roundType, headingRef } = props;
  const { result, previous, best } = report;
  const change = previous === undefined ? undefined : Math.round((result.score - previous) * 100);

  return (
    <section class={`panel round-report band-${result.band.id}-panel`} aria-labelledby="round-report">
      <h2 id="round-report" ref={headingRef} tabIndex={-1}>
        Round report
      </h2>
      <p class="round-score">
        <span class="stat-value">{percent(result.score)}</span> <BandBadge result={result} />
      </p>
      <p>
        In a real interview this round would most likely read as <strong>{result.band.signal}</strong>. You
        answered {result.answered} of {result.total} questions
        {result.minutes !== undefined && ` in ${Math.max(1, Math.round(result.minutes))} min`} (the real round
        is usually about {roundType.minutes} min).
      </p>
      <p>
        {change === undefined
          ? 'This is your first finished attempt at this round - retake it later to see your progress.'
          : change > 0
            ? `Up ${change} points on your previous attempt (${percent(previous!)}).`
            : change < 0
              ? `Down ${-change} points on your previous attempt (${percent(previous!)}) - the areas below show why.`
              : `The same as your previous attempt (${percent(previous!)}).`}
        {best !== undefined && change !== undefined && ` Your best before this was ${percent(best)}.`}
      </p>
      {report.history.length > 1 && (
        <ol class="score-history" aria-label="This round in every attempt">
          {report.history.map((entry) => (
            <li key={entry.attempt}>
              <span class="score-history-label">Attempt {entry.attempt}</span>
              <span class="score-bar" aria-hidden="true">
                <span style={{ width: `${Math.round(entry.score * 100)}%` }} />
              </span>
              <span>{percent(entry.score)}</span>
            </li>
          ))}
        </ol>
      )}

      <h3>What went well</h3>
      {report.strengths.length > 0 ? (
        <ul>
          {report.strengths.map((o) => (
            <li key={o.question.key}>
              {o.question.exercise.title} - {percent(o.credit)}
            </li>
          ))}
        </ul>
      ) : (
        <p>No answer reached 85% this time. The model answers below show what a strong answer covers.</p>
      )}

      {report.improvements.length > 0 && (
        <>
          <h3>Areas to improve</h3>
          <ul class="focus-areas">
            {report.focusAreas.map((area) => (
              <li key={area.name}>
                <strong>{area.name}</strong> <span class="small muted">({area.questions.join('; ')})</span>
                {area.improve && <Markdown source={area.improve} class="small" />}
                {area.href && (
                  <p class="small">
                    <a href={area.href}>Study it</a>
                  </p>
                )}
              </li>
            ))}
          </ul>
          {report.improvements.some((o) => o.missedPoints.length > 0) && (
            <>
              <h4>Points your answers missed</h4>
              <ul>
                {report.improvements
                  .filter((o) => o.missedPoints.length > 0)
                  .map((o) => (
                    <li key={o.question.key}>
                      <em>{o.question.exercise.title}:</em> {o.missedPoints.join('; ')}
                    </li>
                  ))}
              </ul>
            </>
          )}
        </>
      )}

      <h3>Before your next {roundType.title.toLowerCase()} round</h3>
      <ul>
        {roundType.tips.map((tip, i) => (
          <li key={i}>{tip}</li>
        ))}
      </ul>
    </section>
  );
}

function RoundNavigation({
  interview,
  round,
  isLast,
}: {
  interview: MockInterview;
  round: number;
  isLast: boolean;
}) {
  const { update } = useProgress();
  return (
    <div class="row interview-actions">
      {!isLast && (
        <a class="button primary" href={href.interviewRound(interview.id, round + 1)}>
          Next: round {round + 2}
        </a>
      )}
      <a class={`button ${isLast ? 'primary' : 'ghost'}`} href={href.interview(interview.id)}>
        {isLast ? 'See the whole interview' : 'Back to the interview'}
      </a>
      <button
        type="button"
        class="button ghost"
        onClick={() => {
          update((s, now) =>
            startInterviewRound(startInterviewAttempt(s, interview.id, now), interview.id, round, now),
          );
          window.scrollTo(0, 0);
        }}
      >
        Retake this round
      </button>
    </div>
  );
}
