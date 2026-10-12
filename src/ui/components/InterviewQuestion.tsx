/**
 * One question in an interview round. The answer is recorded once per attempt; hints taken
 * before answering reduce its credit. After answering - or once the round is over - the model
 * answer or worked solution is shown, so every round doubles as a lesson in what good looks like.
 */
import type { ComponentChildren } from 'preact';
import { useState } from 'preact/hooks';
import type { Exercise, Practice } from '../../content/schema';
import { isRubricExercise } from '../../content/schema';
import { gradeRubric, HINT_PENALTY } from '../../domain/grading';
import type { ResolvedQuestion } from '../../store/interviews';
import { useProgress } from '../../store/ProgressContext';
import {
  recordInterviewAnswer,
  showInterviewHint,
  type InterviewAnswer,
  type InterviewRoundAttempt,
} from '../../store/state';
import { percent } from './Badges';
import { DebugBody, McqBody, OrderBody, RubricBody, type SubmitArgs } from './ExerciseCard';
import { Markdown } from './Markdown';

const TYPE_LABEL: Record<Exercise['type'], string> = {
  mcq: 'Multiple choice',
  order: 'Put in order',
  debug: 'Find the bug',
  short: 'Short answer',
  testdesign: 'Test design',
  interview: 'Spoken answer - write it down',
  coding: 'Coding - runs on your computer',
};

export function InterviewQuestion(props: {
  interviewId: string;
  roundIndex: number;
  question: ResolvedQuestion;
  number: number;
  total: number;
  record: InterviewRoundAttempt;
  practice?: Practice;
}) {
  const { interviewId, roundIndex, question, number, total, record, practice } = props;
  const { exercise, key, lesson } = question;
  const { update } = useProgress();
  const [details, setDetails] = useState<ComponentChildren>();
  const [draft, setDraft] = useState('');
  const [comparing, setComparing] = useState(false);
  const answer = record.answers[key];
  const finished = Boolean(record.finishedAt);
  const hintsShown = answer ? answer.hintsUsed : (record.hints[key] ?? 0);
  const idPrefix = `iv-${roundIndex}-${key.replace(/[^a-z0-9-]/g, '-')}`;

  const save = (score: number, selfAssessed: boolean, response: string, missed: number[] = []) =>
    update((s, now) =>
      recordInterviewAnswer(s, interviewId, roundIndex, key, { score, selfAssessed, response, missed }, now),
    );
  const submitAuto = ({ score, response, details: shown }: SubmitArgs) => {
    setDetails(shown);
    save(score, false, response);
  };

  return (
    <article
      class="exercise interview-question"
      id={`question-${number}`}
      aria-labelledby={`${idPrefix}-title`}
    >
      <header class="exercise-head">
        <h3 id={`${idPrefix}-title`}>
          <span class="muted">
            {number}/{total}
          </span>{' '}
          {exercise.title}
        </h3>
        <div class="exercise-meta">
          <span class="badge">{TYPE_LABEL[exercise.type]}</span>
          <span class="badge">{lesson ? `From your course: ${lesson.title}` : question.focus.name}</span>
          {isRubricExercise(exercise) && <span class="badge badge-self">Self-assessed</span>}
        </div>
      </header>

      <Markdown source={exercise.prompt} class="exercise-prompt" />

      {!answer && !finished && (
        <>
          {exercise.type === 'mcq' && (
            <McqBody exercise={exercise} idPrefix={idPrefix} locked={false} onSubmit={submitAuto} />
          )}
          {exercise.type === 'order' && (
            <OrderBody exercise={exercise} locked={false} onSubmit={submitAuto} />
          )}
          {exercise.type === 'debug' && (
            <DebugBody exercise={exercise} locked={false} onSubmit={submitAuto} />
          )}
          {isRubricExercise(exercise) && (
            <RubricBody
              exercise={exercise}
              practice={practice}
              idPrefix={idPrefix}
              draft={draft}
              onDraft={setDraft}
              onReveal={() => setComparing(true)}
              onAssess={(covered, response) => {
                const score = gradeRubric(covered.filter(Boolean).length, exercise.rubric.length);
                const missed = covered.flatMap((done, i) => (done ? [] : [i]));
                save(score, true, response, missed);
              }}
              recorded={false}
            />
          )}
        </>
      )}

      {exercise.hints.length > 0 && hintsShown > 0 && (
        <ol class="hints" aria-label="Hints">
          {exercise.hints.slice(0, hintsShown).map((hint, i) => (
            <li key={i}>
              <Markdown source={hint} />
            </li>
          ))}
        </ol>
      )}

      {!answer && !finished && !comparing && (
        <div class="exercise-actions">
          {exercise.hints.length > hintsShown && (
            <button
              type="button"
              class="button secondary"
              onClick={() =>
                update((s) => showInterviewHint(s, interviewId, roundIndex, key, exercise.hints.length))
              }
            >
              Show hint {hintsShown + 1} of {exercise.hints.length} (−{Math.round(HINT_PENALTY * 100)}%
              credit)
            </button>
          )}
          <button type="button" class="button ghost" onClick={() => save(0, false, '(skipped)')}>
            Skip and show the answer
          </button>
        </div>
      )}

      {(answer || finished) && <AnsweredView question={question} answer={answer} details={details} />}
    </article>
  );
}

function AnsweredView(props: {
  question: ResolvedQuestion;
  answer: InterviewAnswer | undefined;
  details: ComponentChildren;
}) {
  const { question, answer, details } = props;
  const { exercise, focus, lesson } = question;
  const credit = answer?.credit ?? 0;
  const verdict = credit >= 0.999 ? 'correct' : credit > 0 ? 'partial' : 'incorrect';
  const skipped = answer?.response === '(skipped)';

  return (
    <>
      <div class={`feedback feedback-${verdict}`} role="status">
        <p class="feedback-title">
          {!answer
            ? 'Not answered.'
            : skipped
              ? 'Skipped.'
              : verdict === 'correct'
                ? 'Full marks.'
                : verdict === 'partial'
                  ? 'Partly there.'
                  : 'Not yet.'}{' '}
          <span class="feedback-score">Score {percent(credit)}</span>
        </p>
        {answer && answer.hintsUsed > 0 && (
          <p class="small">
            {answer.hintsUsed} {answer.hintsUsed === 1 ? 'hint' : 'hints'} used - raw score{' '}
            {percent(answer.score)}.
          </p>
        )}
        {details ?? (answer && !skipped && <StoredResponse exercise={exercise} answer={answer} />)}
        {isRubricExercise(exercise) && answer && !skipped && (
          <p>
            You covered {exercise.rubric.length - answer.missed.length} of {exercise.rubric.length} points.
          </p>
        )}
        {isRubricExercise(exercise) && answer && answer.missed.length > 0 && !skipped && (
          <>
            <p class="feedback-subtitle">Not covered:</p>
            <ul>
              {answer.missed.map((i) => (
                <li key={i}>{exercise.rubric[i]}</li>
              ))}
            </ul>
          </>
        )}
        {credit < 0.85 && focus.href && (
          <p>
            To improve:{' '}
            <a href={focus.href}>
              {lesson
                ? `study "${focus.name}" in ${lesson.title}`
                : `learn more about ${focus.name.toLowerCase()}`}
            </a>
            .
          </p>
        )}
      </div>

      <section class="solution" aria-label="Model answer">
        {isRubricExercise(exercise) && (
          <>
            <h4>{exercise.type === 'coding' ? 'Reference solution' : 'Model answer'}</h4>
            <Markdown source={exercise.modelAnswer} />
            {exercise.type === 'interview' && exercise.followUps.length > 0 && (
              <>
                <h4>Follow-up questions to prepare for</h4>
                <ul>
                  {exercise.followUps.map((followUp, i) => (
                    <li key={i}>
                      <Markdown source={followUp} inline />
                    </li>
                  ))}
                </ul>
              </>
            )}
            <h4>What the interviewer listens for</h4>
            <ul>
              {exercise.rubric.map((point, i) => (
                <li key={i}>{point}</li>
              ))}
            </ul>
          </>
        )}
        <h4>{isRubricExercise(exercise) ? 'Why' : 'Answer'}</h4>
        <Markdown source={exercise.solution} />
      </section>
    </>
  );
}

/** The recorded answer, after a reload: the chosen options, the order or the lines picked. */
function StoredResponse({ exercise, answer }: { exercise: Exercise; answer: InterviewAnswer }) {
  const response = answer.response ?? '';
  if (exercise.type === 'mcq') {
    const chosen = exercise.options.filter((option) => response.split(', ').includes(option.id));
    return (
      <ul class="option-feedback">
        {chosen.map((option) => {
          const right = exercise.correct.includes(option.id);
          return (
            <li key={option.id} class={right ? 'is-right' : 'is-wrong'}>
              <span class="sr-only">{right ? 'Right: ' : 'Wrong: '}</span>
              <Markdown source={option.text} inline class="option-text" /> -{' '}
              <Markdown source={option.feedback} inline />
            </li>
          );
        })}
      </ul>
    );
  }
  if (exercise.type === 'order') {
    const byId = new Map(exercise.items.map((item, i) => [item.id, { item, i }]));
    const order = response.split(' > ').filter((id) => byId.has(id));
    return (
      <ol class="option-feedback">
        {order.map((id, position) => {
          const right = byId.get(id)!.i === position;
          return (
            <li key={id} class={right ? 'is-right' : 'is-wrong'}>
              <span class="sr-only">{right ? 'In the right position: ' : 'Out of position: '}</span>
              <Markdown source={byId.get(id)!.item.text} inline />
            </li>
          );
        })}
      </ol>
    );
  }
  if (exercise.type === 'debug') return <p>You picked {response}.</p>;
  return response ? (
    <details>
      <summary>Your answer</summary>
      <p class="interview-response">{response}</p>
    </details>
  ) : null;
}
