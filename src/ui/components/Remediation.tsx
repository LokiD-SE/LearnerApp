/**
 * "To fix this": after a wrong or partly right answer, point back to the sections that teach
 * the concept and to a similar exercise. Inside the lesson the links scroll; elsewhere (review,
 * practice) they open the lesson at the right place.
 */
import type { Exercise, Lesson } from '../../content/schema';
import { remediationFor } from '../../store/adaptive';
import { useProgress } from '../../store/ProgressContext';
import { focusElement } from '../focus';
import { href } from '../router';

export function Remediation(props: { lesson: Lesson; exercise: Exercise; inLesson: boolean }) {
  const { lesson, exercise, inLesson } = props;
  const { state } = useProgress();
  const { sections, sibling } = remediationFor(lesson, exercise, state);
  if (sections.length === 0 && !sibling) return null;

  const target = (elementId: string, label: string) =>
    inLesson ? (
      <button type="button" class="link-button" onClick={() => focusElement(elementId)}>
        {label}
      </button>
    ) : (
      <a href={href.lesson(lesson.id, elementId)}>{label}</a>
    );

  return (
    <div class="remediation">
      <p class="remediation-title">To fix this</p>
      <ul>
        {sections.length > 0 && (
          <li>
            Re-read{' '}
            {sections.map((section, i) => (
              <span key={section.id}>
                {i > 0 && (i === sections.length - 1 ? ' and ' : ', ')}
                {target(`section-${section.id}`, section.title)}
              </span>
            ))}
            {inLesson ? '' : ` in "${lesson.title}"`}.
          </li>
        )}
        {sibling && <li>Then try a similar exercise: {target(`exercise-${sibling.id}`, sibling.title)}.</li>}
      </ul>
    </div>
  );
}
