// Exercise (react-forms-and-validation): an internal note on a SandPay order, with React 19 form
// Actions. The Action is wired up, but the form has three bugs. Make every test in
// tests/react-forms/order-note-form.test.tsx pass:
//   - "Save note" never shows "Saving..." or disables itself while the note is being saved;
//   - after the server rejects a note, the merchant's text is gone from the textarea;
//   - an empty (or all-spaces) note is sent, and errors are not tied to the textarea
//     (aria-invalid, aria-describedby).
// Keep the label, the button names, the messages and the exported types.
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

export function OrderNoteForm({
  orderId,
  saveNote,
}: {
  orderId: string;
  saveNote: (orderId: string, note: string) => Promise<SaveResult>;
}) {
  async function noteAction(previous: NoteState, formData: FormData): Promise<NoteState> {
    const note = String(formData.get('note') ?? '');
    if (note.length > MAX_NOTE)
      return { ...previous, error: `Keep the note to ${MAX_NOTE} characters or fewer.` };
    const result = await saveNote(orderId, note);
    if (!result.ok) return { ...previous, error: result.error };
    return { draft: '', error: '', saved: previous.saved + 1 };
  }

  const [state, formAction] = useActionState(noteAction, { draft: '', error: '', saved: 0 });
  const { pending } = useFormStatus();
  const id = useId();

  return (
    <form action={formAction} aria-label={`Note for ${orderId}`}>
      <label htmlFor={`${id}-note`}>Internal note</label>
      <textarea id={`${id}-note`} name="note" />
      {state.error && <p>{state.error}</p>}
      {state.saved > 0 && <p role="status">Note saved.</p>}
      <button type="submit" disabled={pending}>
        {pending ? 'Saving...' : 'Save note'}
      </button>
    </form>
  );
}
