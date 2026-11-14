// Reference solution (react-forms-and-validation): an internal note on a SandPay order, written with
// React 19 form Actions - <form action>, useActionState and useFormStatus.
import { useActionState, useId } from 'react';
import { useFormStatus } from 'react-dom';

export type SaveResult = { ok: true } | { ok: false; error: string };

export type NoteState = {
  /** What the textarea shows after the Action - kept on errors, cleared after a save. */
  draft: string;
  error: string;
  saved: number;
};

export const MAX_NOTE = 200;

// useFormStatus reads the status of the <form> this component is rendered inside, so the button must be
// its own component: called in OrderNoteForm itself, it would never see pending.
function SaveButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Saving...' : 'Save note'}
    </button>
  );
}

export function OrderNoteForm({
  orderId,
  saveNote,
}: {
  orderId: string;
  saveNote: (orderId: string, note: string) => Promise<SaveResult>;
}) {
  async function noteAction(previous: NoteState, formData: FormData): Promise<NoteState> {
    const note = String(formData.get('note') ?? '').trim();
    if (note === '') return { ...previous, draft: '', error: 'Write a note first.' };
    if (note.length > MAX_NOTE)
      return { ...previous, draft: note, error: `Keep the note to ${MAX_NOTE} characters or fewer.` };
    const result = await saveNote(orderId, note);
    // React resets uncontrolled fields after the Action, even when it returns an error. Returning the
    // note as the new defaultValue keeps the merchant's text on the screen.
    if (!result.ok) return { ...previous, draft: note, error: result.error };
    return { draft: '', error: '', saved: previous.saved + 1 };
  }

  const [state, formAction] = useActionState(noteAction, { draft: '', error: '', saved: 0 });
  const id = useId();

  return (
    <form action={formAction} aria-label={`Note for ${orderId}`}>
      <label htmlFor={`${id}-note`}>Internal note</label>
      <textarea
        id={`${id}-note`}
        name="note"
        defaultValue={state.draft}
        aria-invalid={state.error ? true : undefined}
        aria-describedby={state.error ? `${id}-error` : undefined}
      />
      {state.error && <p id={`${id}-error`}>{state.error}</p>}
      {state.saved > 0 && <p role="status">Note saved.</p>}
      <SaveButton />
    </form>
  );
}
