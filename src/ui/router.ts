/**
 * Hash routing (`#/lesson/<id>`): works from any static host or sub-path and from a
 * locally opened build, with no server-side rewrites.
 */
import { useEffect, useState } from 'preact/hooks';

export type Route =
  | { name: 'home' }
  | { name: 'learn'; subject?: string; stage?: string }
  | { name: 'lesson'; id: string }
  | { name: 'review' }
  | { name: 'progress' }
  | { name: 'search'; query: string }
  | { name: 'not-found'; path: string };

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
  if (head === 'lesson' && id && parts.length === 2) return { name: 'lesson', id };
  if (head === 'review' && parts.length === 1) return { name: 'review' };
  if (head === 'progress' && parts.length === 1) return { name: 'progress' };
  if (head === 'search' && parts.length === 1) return { name: 'search', query: query.get('q') ?? '' };
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
  lesson: (id: string) => `#/lesson/${encodeURIComponent(id)}`,
  review: () => '#/review',
  progress: () => '#/progress',
  search: (query = '') => (query ? `#/search?q=${encodeURIComponent(query)}` : '#/search'),
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
