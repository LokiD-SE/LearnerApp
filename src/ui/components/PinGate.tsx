import { useEffect, useRef, useState } from 'preact/hooks';
import {
  LOCKOUT_MS,
  MAX_ATTEMPTS,
  RECOVERY_EMAIL,
  isValidPin,
  resetRequestLink,
  setPin,
  verifyPin,
  verifyRecoveryKey,
} from '../../security/pin';
import type { KeyValueStore } from '../../store/storage';

type Mode = 'unlock' | 'change' | 'forgot';

/** Failed attempts per profile for this page load; a lockout follows MAX_ATTEMPTS misses. */
const attempts = new Map<string, { count: number; lockedUntil: number }>();

/** Asks for a profile's 4-digit PIN before signing in; also changes or resets the PIN. */
export function PinGate(props: {
  id: string;
  firstName: string;
  store: KeyValueStore | undefined;
  onUnlock: () => void;
  onCancel: () => void;
}) {
  const { id, firstName, store } = props;
  const [mode, setMode] = useState<Mode>('unlock');
  const [pin, setPinValue] = useState('');
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [message, setMessage] = useState<{ text: string; error: boolean } | undefined>();
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => first.current?.focus(), [mode]);

  const switchMode = (next: Mode) => {
    setMode(next);
    setPinValue('');
    setNewPin('');
    setConfirmPin('');
    setRecoveryKey('');
    setMessage(undefined);
  };

  const lockedFor = () => Math.max(0, (attempts.get(id)?.lockedUntil ?? 0) - Date.now());
  const fail = (text: string) => {
    const entry = attempts.get(id) ?? { count: 0, lockedUntil: 0 };
    entry.count += 1;
    if (entry.count >= MAX_ATTEMPTS) {
      entry.count = 0;
      entry.lockedUntil = Date.now() + LOCKOUT_MS;
      text = `Too many wrong tries. Please wait ${LOCKOUT_MS / 1000} seconds.`;
    }
    attempts.set(id, entry);
    setMessage({ text, error: true });
  };

  const newPinProblem = () => {
    if (!isValidPin(newPin)) return 'The new PIN must be exactly 4 digits';
    if (newPin !== confirmPin) return 'The new PINs do not match';
    return undefined;
  };

  const onSubmit = async (event: Event) => {
    event.preventDefault();
    if (busy) return;
    const wait = lockedFor();
    if (wait > 0) {
      setMessage({
        text: `Too many wrong tries. Please wait ${Math.ceil(wait / 1000)} seconds.`,
        error: true,
      });
      return;
    }
    if (mode !== 'unlock') {
      const problem = newPinProblem();
      if (problem) return setMessage({ text: problem, error: true });
    }
    setBusy(true);
    try {
      if (mode === 'forgot') {
        if (!(await verifyRecoveryKey(recoveryKey))) return fail('That recovery key is not right');
      } else if (!(await verifyPin(store, id, pin))) {
        return fail(isValidPin(pin) ? 'Wrong PIN' : 'Please enter your 4-digit PIN');
      }
      attempts.delete(id);
      if (mode === 'unlock') return props.onUnlock();
      if (!(await setPin(store, id, newPin))) {
        return setMessage({ text: 'The new PIN could not be saved in this browser', error: true });
      }
      switchMode('unlock');
      setMessage({ text: 'PIN changed. Sign in with the new PIN.', error: false });
    } finally {
      setBusy(false);
    }
  };

  const digits = (value: string) => value.replace(/\D/g, '').slice(0, 4);
  const pinField = (
    label: string,
    fieldId: string,
    value: string,
    set: (v: string) => void,
    focus = false,
  ) => (
    <>
      <label class="field-label" for={fieldId}>
        {label}
      </label>
      <input
        id={fieldId}
        ref={focus ? first : undefined}
        type="password"
        inputMode="numeric"
        autocomplete="off"
        maxLength={4}
        value={value}
        onInput={(e) => set(digits(e.currentTarget.value))}
      />
    </>
  );

  const title = { unlock: `Enter PIN for ${firstName}`, change: 'Change PIN', forgot: 'Forgot PIN' }[mode];

  return (
    <form class="card add-profile pin-gate" onSubmit={onSubmit} noValidate>
      <h2>{title}</h2>
      {mode === 'forgot' && (
        <p class="small">
          <a href={resetRequestLink(firstName)}>Email a reset request</a> to {RECOVERY_EMAIL}. You will get a
          recovery key to enter below.
        </p>
      )}
      {mode === 'forgot' ? (
        <>
          <label class="field-label" for="pin-recovery">
            Recovery key
          </label>
          <input
            id="pin-recovery"
            ref={first}
            type="password"
            autocomplete="off"
            value={recoveryKey}
            onInput={(e) => setRecoveryKey(e.currentTarget.value)}
          />
        </>
      ) : (
        pinField(mode === 'change' ? 'Current PIN' : 'PIN', 'pin-current', pin, setPinValue, true)
      )}
      {mode !== 'unlock' && (
        <>
          {pinField('New PIN', 'pin-new', newPin, setNewPin)}
          {pinField('Confirm new PIN', 'pin-confirm', confirmPin, setConfirmPin)}
        </>
      )}
      {message && (
        <p class={message.error ? 'error small' : 'small'} role={message.error ? 'alert' : 'status'}>
          {message.text}
        </p>
      )}
      <p class="pin-actions">
        <button type="submit" class="button primary" disabled={busy}>
          {mode === 'unlock' ? 'Unlock' : mode === 'change' ? 'Change PIN' : 'Reset PIN'}
        </button>
        <button type="button" class="button ghost small" onClick={props.onCancel}>
          Cancel
        </button>
      </p>
      <p class="small">
        {mode !== 'unlock' && (
          <button type="button" class="link-button" onClick={() => switchMode('unlock')}>
            Back to sign in
          </button>
        )}
        {mode !== 'change' && (
          <button type="button" class="link-button" onClick={() => switchMode('change')}>
            Change PIN
          </button>
        )}
        {mode !== 'forgot' && (
          <button type="button" class="link-button" onClick={() => switchMode('forgot')}>
            Forgot PIN?
          </button>
        )}
      </p>
    </form>
  );
}
