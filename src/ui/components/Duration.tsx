import { formatAbout, formatMinutes, isoDuration, type TimeTotal } from '../../content/time';

/** A study time, machine-readable through <time datetime>. */
export const Duration = ({ minutes, about = false }: { minutes: number; about?: boolean }) => (
  <time class="duration" dateTime={isoDuration(minutes)}>
    {about ? formatAbout(minutes) : formatMinutes(minutes)}
  </time>
);

/** The short form for outlines and headings: the published time, or "planned" when nothing is written yet. */
export const ShortTime = ({ total }: { total: TimeTotal }) =>
  total.lessons > 0 ? <Duration minutes={total.minutes} /> : <span class="duration is-planned">planned</span>;

/**
 * The full form for a course or chapter: "6 h 40 min for 8 lessons · 4 h 10 min left ·
 * 3 planned lessons, about 2 h 30 min more". "Left" appears once some of it is done.
 */
export function TimeSummary({ total, left }: { total: TimeTotal; left?: number }) {
  const lessons = (n: number) => `${n} ${n === 1 ? 'lesson' : 'lessons'}`;
  return (
    <p class="time-summary">
      {total.lessons > 0 && (
        <span>
          <Duration minutes={total.minutes} /> for {lessons(total.lessons)}
        </span>
      )}
      {total.lessons > 0 && left !== undefined && left !== total.minutes && (
        <span>
          {left === 0 ? (
            'all done'
          ) : (
            <>
              <Duration minutes={left} /> left
            </>
          )}
        </span>
      )}
      {total.planned > 0 && (
        <span>
          {total.lessons > 0
            ? `${total.planned} planned ${total.planned === 1 ? 'lesson' : 'lessons'}, `
            : `${lessons(total.planned)}, all planned, `}
          <Duration minutes={total.plannedMinutes} about />
          {total.lessons > 0 ? ' more' : ''}
        </span>
      )}
    </p>
  );
}
