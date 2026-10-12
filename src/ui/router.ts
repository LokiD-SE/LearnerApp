/**
 * Hash routing (`#/lesson/<id>`): works from any static host or sub-path and from a
 * locally opened build, with no server-side rewrites.
 */
import { useEffect, useState } from 'preact/hooks';

export type Route =
  | { name: 'home' }
  | { name: 'learn'; subject?: string; stage?: string }
  | { name: 'lesson'; id: string; focus?: string }
  | { name: 'practice'; lesson?: string }
  | { name: 'review' }
  | { name: 'progress' }
  | { name: 'search'; query: string }
  | { name: 'placement'; kind: 'path' | 'lesson'; id: string }
  | { name: 'interviews'; course?: string }
  | { name: 'interview'; id: string }
  /** round is 0-based here and 1-based in the address */
  | { name: 'interview-round'; id: string; round: number }
  | { name: 'not-found'; path: string };

const FOCUS_PATTERN = /^(section|exercise)-[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, '') || '/';
  const [path = '/', queryString = ''] = raw.split('?');
  const query = new URLSearchParams(queryString);
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);

  if (parts.length === 0) return { name: 'home' };
  const [head, id] = parts;
  if (head === 'learn' && parts.length === 1) {
    const route: Route = { name: 'learn' };
    const subject = query.get('subject');
    const stage = query.get('stage');
    if (subject) route.subject = subject;
    if (stage) route.stage = stage;
    return route;
  }
  if (head === 'lesson' && id && parts.length === 2) {
    // focus = the element to scroll to: a section or an exercise of the lesson
    const focus = query.get('focus');
    return focus && FOCUS_PATTERN.test(focus) ? { name: 'lesson', id, focus } : { name: 'lesson', id };
  }
  if (head === 'practice' && parts.length === 1) {
    const lesson = query.get('lesson');
    return lesson ? { name: 'practice', lesson } : { name: 'practice' };
  }
  if (head === 'review' && parts.length === 1) return { name: 'review' };
  if (head === 'progress' && parts.length === 1) return { name: 'progress' };
  if (head === 'search' && parts.length === 1) return { name: 'search', query: query.get('q') ?? '' };
  if (head === 'placement' && parts.length === 3 && (id === 'path' || id === 'lesson')) {
    return { name: 'placement', kind: id, id: parts[2]! };
  }
  if (head === 'interview' && parts.length === 1) {
    const course = query.get('course');
    return course ? { name: 'interviews', course } : { name: 'interviews' };
  }
  if (head === 'interview' && id && parts.length === 2) return { name: 'interview', id };
  if (
    head === 'interview' &&
    id &&
    parts.length === 4 &&
    parts[2] === 'round' &&
    /^[1-9]\d?$/.test(parts[3]!)
  ) {
    return { name: 'interview-round', id, round: Number(parts[3]) - 1 };
  }
  return { name: 'not-found', path };
}

export const href = {
  home: () => '#/',
  learn: (filter: { subject?: string; stage?: string } = {}) => {
    const query = new URLSearchParams();
    if (filter.subject) query.set('subject', filter.subject);
    if (filter.stage) query.set('stage', filter.stage);
    const text = query.toString();
    return text ? `#/learn?${text}` : '#/learn';
  },
  lesson: (id: string, focus?: string) =>
    `#/lesson/${encodeURIComponent(id)}${focus ? `?focus=${encodeURIComponent(focus)}` : ''}`,
  practice: (lesson?: string) => (lesson ? `#/practice?lesson=${encodeURIComponent(lesson)}` : '#/practice'),
  review: () => '#/review',
  progress: () => '#/progress',
  search: (query = '') => (query ? `#/search?q=${encodeURIComponent(query)}` : '#/search'),
  placement: (kind: 'path' | 'lesson', id: string) => `#/placement/${kind}/${encodeURIComponent(id)}`,
  interviews: (course?: string) =>
    course ? `#/interview?course=${encodeURIComponent(course)}` : '#/interview',
  interview: (id: string) => `#/interview/${encodeURIComponent(id)}`,
  /** round is 0-based */
  interviewRound: (id: string, round: number) => `#/interview/${encodeURIComponent(id)}/round/${round + 1}`,
};

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}
