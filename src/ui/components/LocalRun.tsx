/**
 * The "run it on your computer" panel of a coding exercise: which practice project, which
 * files to change, which tests check them, and the command that runs those tests. The
 * project details come from `practice:` in curriculum.yaml, so the panel is content-agnostic.
 */
import type { CodingExercise, Practice } from '../../content/schema';
import { Markdown } from './Markdown';

export const sourceUrl = (practice: Practice, path: string) =>
  `${practice.repository}/blob/${encodeURIComponent(practice.branch)}/${path
    .split('/')
    .map(encodeURIComponent)
    .join('/')}`;

export function LocalRun({ exercise, practice }: { exercise: CodingExercise; practice?: Practice }) {
  const project = practice?.projects.find((p) => p.id === exercise.project);
  const fileLink = (file: string) =>
    practice && project ? (
      <a href={sourceUrl(practice, `${project.path}/${file}`)} target="_blank" rel="noopener noreferrer">
        <code>{file}</code>
      </a>
    ) : (
      <code>{file}</code>
    );

  return (
    <section class="local-run" aria-label="Run it on your computer">
      <h4>Run it on your computer</h4>
      {project && (
        <p>
          Practice project: <strong>{project.title}</strong>, folder <code>{project.path}</code>.
        </p>
      )}
      <dl class="local-run-files">
        <dt>Change</dt>
        <dd>
          <ul>
            {exercise.files.map((file) => (
              <li key={file}>{fileLink(file)}</li>
            ))}
          </ul>
        </dd>
        <dt>Tests that check it</dt>
        <dd>{fileLink(exercise.test)}</dd>
      </dl>
      <p>From the project folder, run:</p>
      <Markdown source={'```bash\n' + exercise.command + '\n```'} />
      {project && (
        <details class="local-run-setup">
          <summary>First time? Get the project and run it</summary>
          <Markdown source={project.setup} />
        </details>
      )}
    </section>
  );
}
