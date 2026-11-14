// @vitest-environment jsdom
import { act, render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { OrderNoteForm, type SaveResult } from '../../exercises/react-forms/OrderNoteForm.js';

// Every answer a test has not settled yet. React 19.2.9 groups (entangles) Transitions while an async
// Action is still running, so one test's unsettled save would keep the next tests' Actions from
// finishing. Settling them after each test keeps every test independent.
const unsettled: ((r: SaveResult) => void)[] = [];
afterEach(async () => {
  await act(async () => {
    for (const settle of unsettled.splice(0)) settle({ ok: true });
  });
});

/** A fake SandPay API whose answers the test settles itself. */
function fakeSave() {
  const calls: [string, string][] = [];
  const answers: ((r: SaveResult) => void)[] = [];
  const saveNote = (orderId: string, note: string) => {
    calls.push([orderId, note]);
    return new Promise<SaveResult>((resolve) => {
      answers.push(resolve);
      unsettled.push(resolve);
    });
  };
  return { calls, answers, saveNote };
}

function setup() {
  const api = fakeSave();
  const user = userEvent.setup();
  render(<OrderNoteForm orderId="ord_1001" saveNote={api.saveNote} />);
  const note = screen.getByRole('textbox', { name: 'Internal note' });
  return { api, user, note };
}

describe('OrderNoteForm', { tags: ['@exercise'] }, () => {
  it('sends the trimmed note for the order', async () => {
    const { api, user, note } = setup();
    await user.type(note, '  Customer called about delivery  ');
    await user.click(screen.getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(api.calls).toEqual([['ord_1001', 'Customer called about delivery']]));
  });

  it('shows a pending button while saving: disabled and "Saving..."', async () => {
    const { api, user, note } = setup();
    await user.type(note, 'Refund approved by Ana');
    await user.click(screen.getByRole('button', { name: 'Save note' }));
    const button = await screen.findByRole('button', { name: 'Saving...' });
    expect(button).toHaveProperty('disabled', true);
    api.answers[0]?.({ ok: true });
    const again = await screen.findByRole('button', { name: 'Save note' });
    expect(again).toHaveProperty('disabled', false);
  });

  it('after a save it says so and clears the note', async () => {
    const { api, user, note } = setup();
    await user.type(note, 'Refund approved by Ana');
    await user.click(screen.getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(api.answers).toHaveLength(1));
    api.answers[0]?.({ ok: true });
    expect((await screen.findByRole('status')).textContent).toBe('Note saved.');
    expect(note).toHaveProperty('value', '');
  });

  it('an empty note is not sent, and the error describes the field', async () => {
    const { api, user, note } = setup();
    await user.type(note, '   ');
    await user.click(screen.getByRole('button', { name: 'Save note' }));
    expect(await screen.findByText('Write a note first.')).toBeTruthy();
    expect(api.calls).toHaveLength(0);
    expect(note.getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById(note.getAttribute('aria-describedby') ?? '')?.textContent).toBe(
      'Write a note first.',
    );
  });

  it('a server error is shown and the merchant keeps the text they wrote', async () => {
    const { api, user, note } = setup();
    await user.type(note, 'Chargeback evidence sent');
    await user.click(screen.getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(api.answers).toHaveLength(1));
    api.answers[0]?.({ ok: false, error: 'Notes are read-only for settled orders.' });
    expect(await screen.findByText('Notes are read-only for settled orders.')).toBeTruthy();
    expect(note).toHaveProperty('value', 'Chargeback evidence sent');
    expect(screen.queryByRole('status')).toBeNull();
  });
});
