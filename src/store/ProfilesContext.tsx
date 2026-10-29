/**
 * Holds the profile list and who is signed in, and saves every change to localStorage.
 * Components change profiles only through `update(fn)`, where fn is one of the pure
 * functions in profiles.ts.
 */
import { createContext, type ComponentChildren } from 'preact';
import { useCallback, useContext, useEffect, useRef, useState } from 'preact/hooks';
import { loadProfiles, saveProfiles, type ProfilesState } from './profiles';
import { browserStore, type KeyValueStore } from './storage';

export interface ProfilesApi {
  state: ProfilesState;
  update: (change: (state: ProfilesState) => ProfilesState) => void;
  /** the store the signed-in profile's progress is kept in */
  store: KeyValueStore | undefined;
  /** Set when the saved profile list could not be read. */
  warning: string | undefined;
  dismissWarning: () => void;
}

const ProfilesContext = createContext<ProfilesApi | null>(null);

export function ProfilesProvider(props: { children: ComponentChildren; store?: KeyValueStore | undefined }) {
  // Chosen once per mount, like ProgressProvider.
  const [store] = useState(() => ('store' in props ? props.store : browserStore()));
  const [initial] = useState(() => loadProfiles(store));
  const [state, setState] = useState(initial.state);
  const [warning, setWarning] = useState(initial.warning);
  const loaded = useRef(true);

  useEffect(() => {
    // loadProfiles already saved what it returned.
    if (loaded.current) {
      loaded.current = false;
      return;
    }
    saveProfiles(store, state);
  }, [state, store]);

  const update = useCallback((change: (state: ProfilesState) => ProfilesState) => setState(change), []);

  const api: ProfilesApi = { state, update, store, warning, dismissWarning: () => setWarning(undefined) };
  return <ProfilesContext.Provider value={api}>{props.children}</ProfilesContext.Provider>;
}

export function useProfiles(): ProfilesApi {
  const api = useContext(ProfilesContext);
  if (!api) throw new Error('useProfiles must be used inside <ProfilesProvider>');
  return api;
}
