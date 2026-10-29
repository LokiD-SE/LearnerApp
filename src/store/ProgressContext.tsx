/**
 * Holds the learner's progress for the UI and saves every change to localStorage.
 * Components change progress only through `update(fn)`, where fn is one of the pure
 * functions in state.ts.
 */
import { createContext, type ComponentChildren } from 'preact';
import { useCallback, useContext, useEffect, useRef, useState } from 'preact/hooks';
import type { ProgressState } from './state';
import { STORAGE_KEY, browserStore, loadProgress, saveProgress, type KeyValueStore } from './storage';

export interface ProgressApi {
  state: ProgressState;
  update: (change: (state: ProgressState, now: Date) => ProgressState) => void;
  replace: (state: ProgressState) => void;
  now: () => Date;
  /** Problems the learner should know about: unreadable or unsaveable progress. */
  warning: string | undefined;
  dismissWarning: () => void;
}

const ProgressContext = createContext<ProgressApi | null>(null);

export function ProgressProvider(props: {
  children: ComponentChildren;
  store?: KeyValueStore | undefined;
  now?: () => Date;
  /** the signed-in profile's progress key; the pre-profiles key when left out (tests) */
  storageKey?: string;
}) {
  // Chosen once per mount: the store and clock do not change while the app runs.
  const [store] = useState(() => ('store' in props ? props.store : browserStore()));
  const [now] = useState(() => props.now ?? (() => new Date()));
  const [key] = useState(() => props.storageKey ?? STORAGE_KEY);
  const [initial] = useState(() => loadProgress(store, now(), key));
  const [state, setState] = useState(initial.state);
  const [warning, setWarning] = useState(initial.warning);
  const loaded = useRef(true);

  useEffect(() => {
    // The first render shows what was loaded; nothing to write yet.
    if (loaded.current) {
      loaded.current = false;
      return;
    }
    const result = saveProgress(store, state, key);
    if (!result.ok) {
      setWarning(
        `Your latest progress could not be saved (${result.error}). Export your progress to keep a copy.`,
      );
    }
  }, [state, store, key]);

  const update = useCallback(
    (change: (state: ProgressState, now: Date) => ProgressState) =>
      setState((current) => change(current, now())),
    [now],
  );

  const api: ProgressApi = {
    state,
    update,
    replace: setState,
    now,
    warning,
    dismissWarning: () => setWarning(undefined),
  };
  return <ProgressContext.Provider value={api}>{props.children}</ProgressContext.Provider>;
}

export function useProgress(): ProgressApi {
  const api = useContext(ProgressContext);
  if (!api) throw new Error('useProgress must be used inside <ProgressProvider>');
  return api;
}
