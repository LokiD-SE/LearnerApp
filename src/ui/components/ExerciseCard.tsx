/**
 * One exercise: answer first, then feedback, progressive hints, a worked solution and a
 * follow-up challenge. The solution stays hidden until the learner has tried (or chooses
 * to give up, which is recorded as a zero-credit attempt).
 *
 * Evidence rules (docs/MASTERY_MODEL.md): only the first submission in a sitting counts
 * as evidence; immediate retries after feedback are practice. Hints taken before that
 * first submission reduce its credit.
 */
import type { ComponentChildren } from 'preact';
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import type {
  DebugExercise,
  Exercise,
  Lesson,
  McqExercise,
  OrderExercise,
  RubricExercise,
} from '../../content/schema';
import { isRubricExercise } from '../../content/schema';
import { creditFor, gradeOrder, gradeRubric, gradeSelection } from '../../domain/grading';
import { useProgress } from '../../store/ProgressContext';
import {
  exerciseOf,
  itemKey,
  recordAttempt,
  saveDraft,
  showHint,
  showSolution,
  startNewEncounter,
} from '../../store/state';
import { SkillBadge, formatDate, percent } from './Badges';
import { Markdown } from './Markdown';
import { highlight } from '../markdown';

type Mode = 'lesson' | 'review';

interface Feedback {
  score: number;
  verdict: 'correct' | 'partial' | 'incorrect';
  details: ComponentChildren;
}

export interface SubmitArgs {
  score: number;
  response: string;
  details: ComponentChildren;
}

const TYPE_LABEL: Record<Exercise['type'], string> = {
  mcq: 'Multiple choice',
  order: 'Put in order',
  debug: 'Debugging',
  short: 'Short answer',
  testdesign: 'Test design',
  interview: 'Interview question',
};

const verdictOf = (score: number): Feedback['verdict'] =>
  score >= 0.999 ? 'correct' : score > 0 ? 'partial' : 'incorrect';

export function ExerciseCard(props: {
  lesson: Lesson;
  exercise: Exercise;
  mode: Mode;
  onRecorded?: (credit: number) => void;
}) {
  const { lesson, exercise, mode, onRecorded } = props;
  const { state, update } = useProgress();
  const key = itemKey(lesson.id, exercise.id);
  const stored = exerciseOf(state, key);
  const [submittedThisView, setSubmittedThisView] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | undefined>();
  const [round, setRound] = useState(0); // remounts the answer inputs on "Try again"
  const [selfAssessing, setSelfAssessing] = useState(false);
  const feedbackRef = useRef<HTMLDivElement>(null);

  // A finished encounter from an earlier visit (or any review) starts fresh: no hints or
  // solution carried over, so the next first try is honest evidence of what is remembered.
  useEffect(() => {
    const previous = exerciseOf(state, key);
    if ((previous.attempts > 0 || mode === 'review') && (previous.hintsShown > 0 || previous.solutionShown)) {
      update((s) => startNewEncounter(s, key));
    }
    // Runs when the exercise changes (on mount), not on every progress update.
  }, [key]);

  const isFirstTry = !submittedThisView && !stored.solutionShown;

  const record = (score: number, response: string, selfAssessed: boolean) => {
    const firstTry = isFirstTry;
    update((s, now) =>
      recordAttempt(
        s,
        {
          lesson,
          itemId: exercise.id,
          kind: 'exercise',
          concept: exercise.concept,
          skill: exercise.skill,
          score,
          hintsUsed: firstTry ? exerciseOf(s, key).hintsShown : 0,
          selfAssessed,
          firstTry,
          mode,
          response,
        },
        now,
      ),
    );
    setSubmittedThisView(true);
    if (onRecorded) onRecorded(creditFor(score, firstTry ? stored.hintsShown : 0));
  };

  const submitAuto = ({ score, response, details }: SubmitArgs) => {
    record(score, response, false);
    setFeedback({ score, verdict: verdictOf(score), details });
    setTimeout(() => feedbackRef.current?.focus(), 0);
  };

  const giveUp = () => {
    if (!submittedThisView && !selfAssessing) {
      record(0, '(gave up and viewed the solution)', false);
      setFeedback({
        score: 0,
        verdict: 'incorrect',
        details: <p>Recorded as not answered. Study the solution, then try the follow-up.</p>,
      });
    }
    update((s) => showSolution(s, key));
  };

  const tryAgain = () => {
    setFeedback(undefined);
    setSelfAssessing(false);
    setRound((r) => r + 1);
  };

  const hintsLeft = exercise.hints.length - stored.hintsShown;
  const answered = submittedThisView || selfAssessing;
  const solutionVisible = stored.solutionShown;

  return (
    <article class="exercise" id={`exercise-${exercise.id}`} aria-labelledby={`${key}-title`}>
      <header class="exercise-head">
        <h3 id={`${key}-title`}>{exercise.title}</h3>
        <div class="exercise-meta">
          <span class="badge">{TYPE_LABEL[exercise.type]}</span>
          <SkillBadge skill={exercise.skill} />
          {isRubricExercise(exercise) && <span class="badge badge-self">Self-assessed</span>}
          {!exercise.required && <span class="badge">Optional</span>}
        </div>
      </header>

      {mode === 'lesson' && stored.attempts > 0 && stored.lastAt && !submittedThisView && (
        <p class="last-result">
          Last result {percent(stored.lastCredit ?? 0)} (first try) on {formatDate(stored.lastAt)} ·{' '}
          {stored.attempts} {stored.attempts === 1 ? 'attempt' : 'attempts'} in total. Answer again to show
          what you remember now.
        </p>
      )}

      <Markdown source={exercise.prompt} class="exercise-prompt" />

      <div key={round}>
        {exercise.type === 'mcq' && (
          <McqBody exercise={exercise} idPrefix={key} locked={Boolean(feedback)} onSubmit={submitAuto} />
        )}
        {exercise.type === 'order' && (
          <OrderBody exercise={exercise} locked={Boolean(feedback)} onSubmit={submitAuto} />
        )}
        {exercise.type === 'debug' && (
          <DebugBody exercise={exercise} locked={Boolean(feedback)} onSubmit={submitAuto} />
        )}
        {isRubricExercise(exercise) && (
          <RubricBody
            exercise={exercise}
            idPrefix={key}
            draft={stored.draft ?? ''}
            onDraft={(text) => update((s) => saveDraft(s, key, text))}
            onReveal={() => setSelfAssessing(true)}
            onAssess={(covered, response) => {
              const score = gradeRubric(covered, exercise.rubric.length);
              record(score, response, true);
              update((s) => saveDraft(s, key, ''));
              setFeedback({
                score,
                verdict: verdictOf(score),
                details: (
                  <p>
                    You covered {covered} of {exercise.rubric.length} rubric points. Self-assessed answers
                    count, but a little less than auto-graded ones.
                  </p>
                ),
              });
            }}
            recorded={Boolean(feedback)}
          />
        )}
      </div>

      <div ref={feedbackRef} tabIndex={-1} class="feedback-region" aria-live="polite">
        {feedback && (
          <div class={`feedback feedback-${feedback.verdict}`}>
            <p class="feedback-title">
              {feedback.verdict === 'correct'
                ? 'Correct.'
                : feedback.verdict === 'partial'
                  ? 'Partly right.'
                  : 'Not yet.'}{' '}
              <span class="feedback-score">Score {percent(feedback.score)}</span>
            </p>
            {feedback.details}
          </div>
        )}
      </div>

      {exercise.hints.length > 0 && stored.hintsShown > 0 && (
        <ol class="hints" aria-label="Hints">
          {exercise.hints.slice(0, stored.hintsShown).map((hint, index) => (
            <li key={index}>
              <Markdown source={hint} />
            </li>
          ))}
        </ol>
      )}

      <div class="exercise-actions">
        {exercise.hints.length > 0 && !solutionVisible && (
          <button
            type="button"
            class="button secondary"
            disabled={hintsLeft <= 0}
            onClick={() => update((s) => showHint(s, key, exercise.hints.length))}
          >
            {hintsLeft > 0
              ? `Show hint ${stored.hintsShown + 1} of ${exercise.hints.length}`
              : 'No more hints'}
          </button>
        )}
        {feedback && feedback.verdict !== 'correct' && !solutionVisible && !isRubricExercise(exercise) && (
          <button type="button" class="button secondary" onClick={tryAgain}>
            Try again
          </button>
        )}
        {!solutionVisible && (
          <button type="button" class="button ghost" onClick={giveUp}>
            {answered ? 'Show worked solution' : 'Give up and show solution'}
          </button>
        )}
      </div>

      {solutionVisible && (
        <section class="solution" aria-label="Worked solution">
          <h4>Worked solution</h4>
          <Markdown source={exercise.solution} />
          {exercise.followUp && (
            <div class="follow-up">
              <h4>Try this next</h4>
              <Markdown source={exercise.followUp} />
            </div>
          )}
        </section>
      )}
    </article>
  );
}

/* ---------------------------------------------------------------- multiple choice */

export function McqBody(props: {
  submitLabel?: string;
  exercise: McqExercise;
  idPrefix: string;
  locked: boolean;
  onSubmit: (args: SubmitArgs) => void;
}) {
  const { exercise, idPrefix, locked, onSubmit } = props;
  const multiple = exercise.correct.length > 1;
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (id: string) =>
    setSelected((current) =>
      multiple ? (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]) : [id],
    );

  const submit = () => {
    const result = gradeSelection(selected, exercise.correct);
    const chosen = exercise.options.filter((o) => selected.includes(o.id));
    onSubmit({
      score: result.score,
      response: chosen.map((o) => o.id).join(', '),
      details: (
        <>
          <ul class="option-feedback">
            {chosen.map((option) => (
              <li key={option.id} class={exercise.correct.includes(option.id) ? 'is-right' : 'is-wrong'}>
                <span class="sr-only">{exercise.correct.includes(option.id) ? 'Right: ' : 'Wrong: '}</span>
                <Markdown source={option.text} inline class="option-text" /> -{' '}
                <Markdown source={option.feedback} inline />
              </li>
            ))}
          </ul>
          {result.missed.length > 0 && (
            <p>
              You missed {result.missed.length} correct {result.missed.length === 1 ? 'option' : 'options'}.
              Take a hint or try again before looking at the solution.
            </p>
          )}
        </>
      ),
    });
  };

  return (
    <fieldset class="options" disabled={locked}>
      <legend class="sr-only">Answer options</legend>
      {multiple && <p class="instruction">Select every option that applies.</p>}
      {exercise.options.map((option) => {
        const id = `${idPrefix}-opt-${option.id}`;
        return (
          <label
            key={option.id}
            class={`option ${selected.includes(option.id) ? 'is-selected' : ''}`}
            for={id}
          >
            <input
              id={id}
              type={multiple ? 'checkbox' : 'radio'}
              name={`${idPrefix}-options`}
              checked={selected.includes(option.id)}
              onChange={() => toggle(option.id)}
            />
            <Markdown source={option.text} inline />
          </label>
        );
      })}
      <button
        type="button"
        class="button primary"
        disabled={selected.length === 0 || locked}
        onClick={submit}
      >
        {props.submitLabel ?? 'Check answer'}
      </button>
    </fieldset>
  );
}

/* ---------------------------------------------------------------- ordering */

/** Deterministic shuffle (so the page doesn't reshuffle on every render) that never
 * starts in the correct order. */
export function initialOrder(ids: readonly string[], seed: string): string[] {
  let hash = 2166136261;
  for (const char of seed) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  const next = () => {
    hash = Math.imul(hash ^ (hash >>> 15), 2246822507) >>> 0;
    return hash / 2 ** 32;
  };
  const result = [...ids];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(next() * (i + 1));
    [result[i], result[j]] = [result[j]!, result[i]!];
  }
  if (result.every((id, index) => id === ids[index]) && result.length > 1) result.push(result.shift()!);
  return result;
}

export function OrderBody(props: {
  submitLabel?: string;
  exercise: OrderExercise;
  locked: boolean;
  onSubmit: (args: SubmitArgs) => void;
}) {
  const { exercise, locked, onSubmit } = props;
  const correct = exercise.items.map((item) => item.id);
  const [order, setOrder] = useState(() => initialOrder(correct, exercise.id));
  const [checked, setChecked] = useState<boolean[] | undefined>();
  const byId = useMemo(() => new Map(exercise.items.map((item) => [item.id, item])), [exercise]);

  const move = (index: number, delta: number) =>
    setOrder((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target]!, next[index]!];
      return next;
    });

  const submit = () => {
    const score = gradeOrder(order, correct);
    const inPlace = order.map((id, index) => correct[index] === id);
    setChecked(inPlace);
    onSubmit({
      score,
      response: order.join(' > '),
      details: (
        <p>
          {inPlace.filter(Boolean).length} of {order.length} steps are in the right position (marked with a
          tick).
        </p>
      ),
    });
  };

  return (
    <div class="order">
      <ol class="order-list">
        {order.map((id, index) => (
          <li key={id} class={checked ? (checked[index] ? 'is-right' : 'is-wrong') : ''}>
            <span class="order-text">
              {checked && <span aria-hidden="true">{checked[index] ? '✓ ' : '✗ '}</span>}
              {checked && (
                <span class="sr-only">
                  {checked[index] ? 'In the right position: ' : 'Out of position: '}
                </span>
              )}
              <Markdown source={byId.get(id)!.text} inline />
            </span>
            <span class="order-buttons">
              <button
                type="button"
                class="icon-button"
                disabled={locked || index === 0}
                aria-label={`Move "${byId.get(id)!.text}" up`}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                class="icon-button"
                disabled={locked || index === order.length - 1}
                aria-label={`Move "${byId.get(id)!.text}" down`}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
            </span>
          </li>
        ))}
      </ol>
      <button type="button" class="button primary" disabled={locked} onClick={submit}>
        {props.submitLabel ?? 'Check order'}
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------- debugging */

export function DebugBody(props: {
  submitLabel?: string;
  exercise: DebugExercise;
  locked: boolean;
  onSubmit: (args: SubmitArgs) => void;
}) {
  const { exercise, locked, onSubmit } = props;
  const lines = useMemo(() => exercise.code.replace(/\n$/, '').split('\n'), [exercise.code]);
  const [selected, setSelected] = useState<number[]>([]);

  const toggle = (line: number) =>
    setSelected((current) =>
      current.includes(line) ? current.filter((l) => l !== line) : [...current, line].sort((a, b) => a - b),
    );

  const submit = () => {
    const result = gradeSelection(selected.map(String), exercise.correctLines.map(String));
    const notes = exercise.lineNotes.filter((note) => result.wrong.includes(String(note.line)));
    onSubmit({
      score: result.score,
      response: `lines ${selected.join(', ')}`,
      details: (
        <>
          <p>
            {result.hits.length} of {exercise.correctLines.length} defect{' '}
            {exercise.correctLines.length === 1 ? 'line' : 'lines'} found
            {result.wrong.length > 0 ? `, ${result.wrong.length} not part of the defect` : ''}.
          </p>
          {notes.length > 0 && (
            <ul>
              {notes.map((note) => (
                <li key={note.line}>
                  <strong>Line {note.line}:</strong> <Markdown source={note.note} inline />
                </li>
              ))}
            </ul>
          )}
        </>
      ),
    });
  };

  return (
    <div class="debug">
      <p class="instruction">Tap the line numbers or lines you think are responsible.</p>
      <div class="code-block code-lines" role="group" aria-label="Code lines">
        <span class="code-lang">{exercise.language}</span>
        {lines.map((text, index) => {
          const line = index + 1;
          const on = selected.includes(line);
          return (
            <button
              key={line}
              type="button"
              class={`code-line ${on ? 'is-selected' : ''}`}
              aria-pressed={on}
              aria-label={`Line ${line}: ${text.trim() || 'blank'}`}
              disabled={locked}
              onClick={() => toggle(line)}
            >
              <span class="line-number" aria-hidden="true">
                {line}
              </span>
              <code
                class="hljs"
                dangerouslySetInnerHTML={{ __html: highlight(text, exercise.language) || '&nbsp;' }}
              />
            </button>
          );
        })}
      </div>
      <button
        type="button"
        class="button primary"
        disabled={locked || selected.length === 0}
        onClick={submit}
      >
        {props.submitLabel ?? 'Check lines'}
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------- free text, self-assessed */

const MIN_ANSWER_CHARS = 20;

function RubricBody(props: {
  exercise: RubricExercise;
  idPrefix: string;
  draft: string;
  onDraft: (text: string) => void;
  onReveal: () => void;
  onAssess: (covered: number, response: string) => void;
  recorded: boolean;
}) {
  const { exercise, idPrefix, onDraft, onReveal, onAssess, recorded } = props;
  const [text, setText] = useState(props.draft);
  const [revealed, setRevealed] = useState(false);
  const [covered, setCovered] = useState<boolean[]>(() => exercise.rubric.map(() => false));
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();

  const onInput = (value: string) => {
    setText(value);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => onDraft(value), 400);
  };
  useEffect(() => () => clearTimeout(saveTimer.current), []);

  const tooShort = text.trim().length < MIN_ANSWER_CHARS;
  const answerId = `${idPrefix}-answer`;

  return (
    <div class="rubric-exercise">
      <label for={answerId} class="field-label">
        Your answer
      </label>
      <textarea
        id={answerId}
        rows={exercise.type === 'testdesign' ? 10 : 5}
        value={text}
        readOnly={revealed}
        onInput={(event) => onInput((event.target as HTMLTextAreaElement).value)}
        placeholder={
          exercise.type === 'testdesign'
            ? 'Precondition / steps / expected result / evidence, one case per paragraph'
            : 'Write your answer before you compare it'
        }
      />
      {!revealed && (
        <div class="row">
          <button
            type="button"
            class="button primary"
            disabled={tooShort}
            onClick={() => {
              clearTimeout(saveTimer.current);
              onDraft(text);
              setRevealed(true);
              onReveal();
            }}
          >
            Compare with the model answer
          </button>
          {tooShort && <span class="hint-text">Write at least a couple of sentences first.</span>}
        </div>
      )}

      {revealed && (
        <div class="model-answer">
          <h4>Model answer</h4>
          <Markdown source={exercise.modelAnswer} />
          {exercise.type === 'interview' && exercise.followUps.length > 0 && (
            <>
              <h4>Follow-up questions the interviewer may ask</h4>
              <ul>
                {exercise.followUps.map((question, index) => (
                  <li key={index}>
                    <Markdown source={question} inline />
                  </li>
                ))}
              </ul>
            </>
          )}
          <fieldset class="rubric" disabled={recorded}>
            <legend>Tick only what your answer really covered</legend>
            {exercise.rubric.map((item, index) => {
              const id = `${idPrefix}-rubric-${index}`;
              return (
                <label key={index} class="option" for={id}>
                  <input
                    id={id}
                    type="checkbox"
                    checked={covered[index]}
                    onChange={() =>
                      setCovered((current) => current.map((value, i) => (i === index ? !value : value)))
                    }
                  />
                  <span>{item}</span>
                </label>
              );
            })}
            {!recorded && (
              <button
                type="button"
                class="button primary"
                onClick={() => onAssess(covered.filter(Boolean).length, text)}
              >
                Save my self-assessment
              </button>
            )}
          </fieldset>
        </div>
      )}
    </div>
  );
}
