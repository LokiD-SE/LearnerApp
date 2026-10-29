import { useEffect, useState } from 'preact/hooks';
import { useProfiles } from '../../store/ProfilesContext';
import { MAX_NAME_LENGTH, addProfile, signIn, validateFirstName } from '../../store/profiles';

/** Shown when nobody is signed in: pick a profile (no password) or add one. */
export function ProfilesPage() {
  const { state, update, warning, dismissWarning } = useProfiles();
  const [name, setName] = useState('');
  const [error, setError] = useState<string | undefined>();
  const profiles = Object.entries(state.profiles);

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('main h1');
    heading?.focus({ preventScroll: true });
    document.title = 'Who is learning? - LearnerApp';
  }, []);

  // Typing shows a rule problem straight away; an empty box is only an error on submit.
  const onInput = (value: string) => {
    setName(value);
    const result = validateFirstName(value, state);
    setError(value.trim() === '' || result.ok ? undefined : result.error);
  };

  const onSubmit = (event: Event) => {
    event.preventDefault();
    const result = validateFirstName(name, state);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    update((current) => addProfile(current, result.firstName));
  };

  return (
    <main id="main" tabIndex={-1} class="page narrow profiles-page">
      <p class="brand">
        <span class="brand-mark" aria-hidden="true">
          L
        </span>{' '}
        LearnerApp
      </p>
      {warning && (
        <div class="banner" role="alert">
          <p>{warning}</p>
          <button type="button" class="button ghost small" onClick={dismissWarning}>
            Dismiss
          </button>
        </div>
      )}
      <h1 tabIndex={-1}>Who is learning?</h1>
      <p class="lead">Pick your profile. Each profile keeps its own progress on this device.</p>

      <ul class="profile-list" aria-label="Profiles">
        {profiles.map(([id, profile]) => (
          <li key={id}>
            <button
              type="button"
              class="profile-button"
              onClick={() => update((current) => signIn(current, id))}
            >
              <span class="profile-avatar" aria-hidden="true">
                {profile.firstName.charAt(0)}
              </span>
              <span class="profile-name">{profile.firstName}</span>
              <span class="small muted">
                {profile.completedLessons.length} lessons · {profile.progressPercentage}%
              </span>
            </button>
          </li>
        ))}
      </ul>

      <form class="card add-profile" onSubmit={onSubmit} noValidate>
        <h2>Add a profile</h2>
        <label class="field-label" for="new-profile-name">
          First name
        </label>
        <div class="search-form">
          <input
            id="new-profile-name"
            type="text"
            autocomplete="given-name"
            maxLength={MAX_NAME_LENGTH + 10}
            value={name}
            onInput={(e) => onInput(e.currentTarget.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'new-profile-error' : 'new-profile-help'}
          />
          <button type="submit" class="button primary">
            Add and start
          </button>
        </div>
        {error ? (
          <p id="new-profile-error" class="error small" role="alert">
            {error}
          </p>
        ) : (
          <p id="new-profile-help" class="small muted">
            One word, letters only. The first letter is capitalised for you.
          </p>
        )}
      </form>
    </main>
  );
}
