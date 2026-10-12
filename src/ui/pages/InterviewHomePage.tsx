/**
 * Interview practice: generate a practice interview for a course, in the style of a company's
 * reported interview loop, and get back to the interviews generated before.
 */
import { useState } from 'preact/hooks';
import type { InterviewProfile } from '../../content/schema';
import type { ContentIndex, InterviewContent } from '../../content/validate';
import {
  attemptSummaries,
  courseKey,
  courseOf,
  generateInterview,
  interviewCourses,
  newSeed,
  parseCourseKey,
} from '../../store/interviews';
import { useProgress } from '../../store/ProgressContext';
import { addInterview } from '../../store/state';
import { formatDate, percent } from '../components/Badges';
import { Markdown } from '../components/Markdown';
import { href } from '../router';

export function InterviewHomePage({ index, course }: { index: ContentIndex; course?: string }) {
  const { state, update } = useProgress();
  const content = index.interviews;
  const courses = interviewCourses(index);
  const [selectedCourse, setCourse] = useState(() =>
    course && courses.some((c) => c.key === course) ? course : (courses[0]?.key ?? ''),
  );
  const [profileId, setProfile] = useState('any');
  const [error, setError] = useState<string>();

  if (!content || courses.length === 0) {
    return (
      <section class="page narrow">
        <h1 tabIndex={-1}>Interview practice</h1>
        <div class="empty-state">
          <p>Interview practice needs published lessons and interview content.</p>
        </div>
      </section>
    );
  }

  const paths = courses.filter((c) => c.ref.kind === 'path');
  const tracks = courses.filter((c) => c.ref.kind === 'subject');
  const chosenProfile = content.profiles.find((p) => p.id === profileId);

  const generate = () => {
    const ref = parseCourseKey(selectedCourse);
    const generated =
      ref &&
      generateInterview(index, { course: ref, profileId, seed: newSeed(), previous: state.interviews });
    if (!generated || generated.rounds.length === 0) {
      setError('No interview could be generated for this course. Try another course or company.');
      return;
    }
    const id = `iv-${Date.now().toString(36)}-${generated.seed.toString(36)}`;
    update((s, now) => addInterview(s, { ...generated, id, createdAt: now.toISOString(), attempts: [] }));
    window.location.hash = href.interview(id);
  };

  const mine = [...state.interviews].reverse();

  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>Interview practice</h1>
      <p class="lead">
        Practise the interview rounds that big tech, the Big 4, IT-services MNCs, mid-market product companies
        and startups are reported to use - with questions on your course. Every round ends with a score, model
        answers, what went well and what to improve. Retake an interview as often as you like and compare your
        rounds; generate a new one for a different set of rounds and questions.
      </p>

      <form
        class="panel interview-form"
        onSubmit={(event) => {
          event.preventDefault();
          generate();
        }}
      >
        <h2 class="panel-title">Generate an interview</h2>
        <label class="field-label" for="interview-course">
          Course
        </label>
        <select
          id="interview-course"
          value={selectedCourse}
          onChange={(e) => {
            setCourse((e.target as HTMLSelectElement).value);
            setError(undefined);
          }}
        >
          <optgroup label="Learning paths">
            {paths.map((c) => (
              <option key={c.key} value={c.key}>
                {c.title}
              </option>
            ))}
          </optgroup>
          <optgroup label="Tracks">
            {tracks.map((c) => (
              <option key={c.key} value={c.key}>
                {c.title}
              </option>
            ))}
          </optgroup>
        </select>
        <label class="field-label" for="interview-company">
          Company style
        </label>
        <select
          id="interview-company"
          value={profileId}
          onChange={(e) => setProfile((e.target as HTMLSelectElement).value)}
        >
          <option value="any">Any - a different company each time</option>
          {content.profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <p class="small muted">
          {chosenProfile
            ? chosenProfile.summary
            : 'Each new interview picks a company style, which of its rounds you get, and questions you have not seen yet.'}
        </p>
        <div class="row">
          <button type="submit" class="button primary">
            Generate interview
          </button>
        </div>
        {error && (
          <p class="error" role="alert">
            {error}
          </p>
        )}
      </form>

      {mine.length > 0 && (
        <section aria-labelledby="my-interviews">
          <h2 id="my-interviews">Your interviews</h2>
          <ul class="interview-list">
            {mine.map((interview) => {
              const profile = content.profiles.find((p) => p.id === interview.profileId);
              const courseTitle = courseOf(index, interview.course)?.title ?? courseKey(interview.course);
              const summaries = attemptSummaries(index, interview);
              const latest = summaries.at(-1);
              const best = Math.max(...summaries.map((s) => (s.complete ? (s.overall ?? 0) : 0)), 0);
              return (
                <li key={interview.id} class="card">
                  <h3>
                    <a href={href.interview(interview.id)}>{profile?.name ?? 'Interview'}</a>
                  </h3>
                  <p class="small muted">
                    {courseTitle} · {interview.rounds.length} rounds · generated{' '}
                    {formatDate(interview.createdAt)}
                  </p>
                  <p class="small">
                    {summaries.length === 0
                      ? 'Not started yet.'
                      : `${summaries.length} ${summaries.length === 1 ? 'attempt' : 'attempts'}` +
                        (latest?.overall !== undefined ? ` · latest ${percent(latest.overall)}` : '') +
                        (best > 0 ? ` · best complete ${percent(best)}` : '')}
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <CompanyLoops content={content} />
    </section>
  );
}

function CompanyLoops({ content }: { content: InterviewContent }) {
  return (
    <section aria-labelledby="company-loops">
      <h2 id="company-loops">How these companies interview</h2>
      <p class="small muted">Checked against the sources on {formatDate(`${content.asOf}T12:00:00`)}.</p>
      <Markdown source={content.note} class="small" />
      {content.profiles.map((profile) => (
        <details key={profile.id} class="panel company-loop">
          <summary>
            <strong>{profile.name}</strong> <span class="muted small">· {profile.category}</span>
          </summary>
          <ProfileDetails profile={profile} content={content} />
        </details>
      ))}
    </section>
  );
}

export function ProfileDetails({
  profile,
  content,
}: {
  profile: InterviewProfile;
  content: InterviewContent;
}) {
  const title = (id: string) => content.roundTypes.get(id)?.title ?? id;
  return (
    <div class="profile-details">
      <p>{profile.summary}</p>
      <h4>The reported loop</h4>
      <ol>
        {profile.stages.map((stage, i) => (
          <li key={i}>
            <strong>{stage.label}</strong> - {stage.rounds.map(title).join(' or ')}
            {stage.chance !== undefined && <span class="muted"> (not every candidate)</span>}
          </li>
        ))}
      </ol>
      {profile.notes.length > 0 && (
        <ul>
          {profile.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}
      <h4>Sources</h4>
      <ul class="small">
        {profile.sources.map((source) => (
          <li key={source.url}>
            <a href={source.url} target="_blank" rel="noopener noreferrer">
              {source.title}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
