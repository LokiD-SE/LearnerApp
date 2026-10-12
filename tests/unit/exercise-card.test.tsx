import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';
import { ProgressProvider } from '../../src/store/ProgressContext';
import { STORAGE_KEY, parseProgress } from '../../src/store/storage';
import { ExerciseCard } from '../../src/ui/components/ExerciseCard';
import { memoryStore, realIndex } from './helpers';

const lesson = realIndex().lessons.get('idempotency-keys')!;
const exercise = (id: string) => lesson.exercises.find((e) => e.id === id)!;
const fixedNow = () => new Date('2026-10-01T09:00:00.000Z');

function setup(id: string, store = memoryStore()) {
  render(
    <ProgressProvider store={store} now={fixedNow}>
      <ExerciseCard lesson={lesson} exercise={exercise(id)} mode="lesson" />
    </ProgressProvider>,
  );
  const saved = () => {
    const raw = store.data[STORAGE_KEY];
    if (!raw) return undefined;
    const parsed = parseProgress(raw);
    if (!parsed.ok) throw new Error(parsed.error);
    return parsed.state;
  };
  return { store, saved };
}

afterEach(cleanup);

describe('ExerciseCard - multiple choice', () => {
  it('gives misconception feedback for a wrong answer without revealing the solution', async () => {
    const { saved } = setup('duplicate-charge-rca');
    expect(screen.queryByText('Worked solution')).toBeNull();

    fireEvent.click(screen.getByLabelText(/race condition in the server/i));
    fireEvent.click(screen.getByRole('button', { name: 'Check answer' }));

    expect(await screen.findByText('Not yet.')).toBeTruthy();
    expect(screen.getByText(/A race needs two requests with the/)).toBeTruthy();
    expect(screen.queryByText('Worked solution')).toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();

    await waitFor(() => expect(saved()?.attempts).toHaveLength(1));
    expect(saved()!.attempts[0]).toMatchObject({
      itemId: 'duplicate-charge-rca',
      score: 0,
      firstTry: true,
      mode: 'lesson',
    });
  });

  it('a retry after feedback is recorded as practice, not evidence', async () => {
    const { saved } = setup('duplicate-charge-rca');
    fireEvent.click(screen.getByLabelText(/race condition in the server/i));
    fireEvent.click(screen.getByRole('button', { name: 'Check answer' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    fireEvent.click(screen.getByLabelText(/generated a new key/i));
    fireEvent.click(screen.getByRole('button', { name: 'Check answer' }));
    expect(await screen.findByText('Correct.')).toBeTruthy();
    await waitFor(() => expect(saved()?.attempts).toHaveLength(2));
    expect(saved()!.attempts.map((a) => a.firstTry)).toEqual([true, false]);
  });

  it('hints are progressive and reduce the credit of the first answer', async () => {
    const { saved } = setup('methods-idempotent');
    fireEvent.click(screen.getByRole('button', { name: 'Show hint 1 of 2' }));
    const hints = await screen.findByRole('list', { name: 'Hints' });
    expect(hints.textContent).toMatch(/Idempotency is about the effect on the server/);
    expect(hints.querySelectorAll('li')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Show hint 2 of 2' })).toBeTruthy();

    for (const label of ['`GET`', '`PUT`', '`DELETE`']) {
      fireEvent.click(screen.getByLabelText(label.replace(/`/g, '')));
    }
    fireEvent.click(screen.getByRole('button', { name: 'Check answer' }));
    expect(await screen.findByText('Correct.')).toBeTruthy();
    await waitFor(() => expect(saved()?.attempts).toHaveLength(1));
    expect(saved()!.attempts[0]).toMatchObject({ score: 1, hintsUsed: 1, credit: 0.85 });
  });

  it('giving up records zero credit and shows the worked solution and follow-up', async () => {
    const { saved } = setup('which-need-keys');
    fireEvent.click(screen.getByRole('button', { name: 'Give up and show solution' }));
    expect(await screen.findByText('Worked solution')).toBeTruthy();
    expect(screen.getByText('Try this next')).toBeTruthy();
    await waitFor(() => expect(saved()?.attempts).toHaveLength(1));
    expect(saved()!.attempts[0]).toMatchObject({ score: 0, credit: 0, firstTry: true });
  });
});

describe('ExerciseCard - debugging', () => {
  it('grades selected lines and explains a wrongly picked line', async () => {
    const { saved } = setup('race-condition-debug');
    fireEvent.click(screen.getByRole('button', { name: /^Line 2:/ }));
    fireEvent.click(screen.getByRole('button', { name: /^Line 6:/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Check lines' }));
    expect(await screen.findByText('Not yet.')).toBeTruthy(); // one right, one wrong = 0
    expect(screen.getByText(/Charging is the side effect that gets duplicated/)).toBeTruthy();
    await waitFor(() => expect(saved()?.attempts[0]?.response).toBe('lines 2, 6'));
  });
});

describe('ExerciseCard - self-assessed answers', () => {
  it('needs an answer before showing the model answer, then records the rubric score', async () => {
    const { saved } = setup('retry-same-key-explain');
    const compare = screen.getByRole('button', { name: 'Compare with the model answer' });
    expect((compare as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText('Model answer')).toBeNull();

    fireEvent.input(screen.getByLabelText('Your answer'), {
      target: {
        value:
          'The outcome is unknown after a timeout, so the same key lets the server replay instead of charging again.',
      },
    });
    fireEvent.click(compare);
    expect(await screen.findByText('Model answer')).toBeTruthy();

    const rubric = screen.getAllByRole('checkbox');
    expect(rubric).toHaveLength(4);
    fireEvent.click(rubric[0]!);
    fireEvent.click(rubric[1]!);
    fireEvent.click(screen.getByRole('button', { name: 'Save my self-assessment' }));
    expect(await screen.findByText(/You covered 2 of 4 rubric points/)).toBeTruthy();

    await waitFor(() => expect(saved()?.attempts).toHaveLength(1));
    expect(saved()!.attempts[0]).toMatchObject({ score: 0.5, selfAssessed: true });
    expect(saved()!.attempts[0]!.response).toMatch(/outcome is unknown/);
  });
});

describe('ExerciseCard - coding exercises', () => {
  it('shows where to run the exercise, then compares with the reference solution', async () => {
    const index = realIndex();
    const javaLesson = index.lessons.get('java-equals-hashcode')!;
    const coding = javaLesson.exercises.find((e) => e.id === 'implement-money-equality')!;
    const store = memoryStore();
    render(
      <ProgressProvider store={store} now={fixedNow}>
        <ExerciseCard
          lesson={javaLesson}
          exercise={coding}
          mode="lesson"
          practice={index.curriculum.practice}
        />
      </ProgressProvider>,
    );

    expect(screen.getByText('Coding - runs on your computer')).toBeTruthy();
    const panel = screen.getByRole('region', { name: 'Run it on your computer' });
    const fileLink = within(panel).getByRole('link', {
      name: 'src/exercises/java/learnerapp/equality/Money.java',
    });
    expect(fileLink.getAttribute('href')).toBe(
      'https://github.com/LokiD-SE/LearnerApp/blob/main/practice/java/src/exercises/java/learnerapp/equality/Money.java',
    );
    expect(fileLink.getAttribute('rel')).toContain('noopener');
    expect(panel.textContent).toContain('mvn test -Dtest=MoneyTest');
    expect(within(panel).getByText('First time? Get the project and run it')).toBeTruthy();

    fireEvent.input(screen.getByLabelText('Your result'), {
      target: {
        value: 'Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 - after adding equals and hashCode',
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Compare with the reference solution' }));
    expect(await screen.findByText('Reference solution')).toBeTruthy();
    fireEvent.click(screen.getAllByRole('checkbox')[0]!);
    fireEvent.click(screen.getByRole('button', { name: 'Save my self-assessment' }));
    expect(await screen.findByText(/You covered 1 of 4 rubric points/)).toBeTruthy();
  });
});
