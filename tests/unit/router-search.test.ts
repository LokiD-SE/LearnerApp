import { describe, expect, it } from 'vitest';
import { searchContent } from '../../src/content/search';
import { href, parseHash } from '../../src/ui/router';
import { realIndex } from './helpers';

describe('parseHash', () => {
  it('parses every route', () => {
    expect(parseHash('')).toEqual({ name: 'home' });
    expect(parseHash('#/')).toEqual({ name: 'home' });
    expect(parseHash('#/learn')).toEqual({ name: 'learn' });
    expect(parseHash('#/learn?subject=api-testing&stage=stage-2')).toEqual({
      name: 'learn',
      subject: 'api-testing',
      stage: 'stage-2',
    });
    expect(parseHash('#/lesson/idempotency-keys')).toEqual({ name: 'lesson', id: 'idempotency-keys' });
    expect(parseHash('#/review')).toEqual({ name: 'review' });
    expect(parseHash('#/progress')).toEqual({ name: 'progress' });
    expect(parseHash('#/search?q=refund%20timeout')).toEqual({ name: 'search', query: 'refund timeout' });
    expect(parseHash('#/nowhere/at/all')).toEqual({ name: 'not-found', path: '/nowhere/at/all' });
  });
  it('round-trips the href helpers', () => {
    expect(parseHash(href.learn({ subject: 'java' }))).toEqual({ name: 'learn', subject: 'java' });
    expect(parseHash(href.search('a&b'))).toEqual({ name: 'search', query: 'a&b' });
    expect(parseHash(href.lesson('x-y'))).toEqual({ name: 'lesson', id: 'x-y' });
  });
});

describe('searchContent', () => {
  const index = realIndex();
  it('finds the lesson by a concept word, best match first', () => {
    const hits = searchContent(index, 'idempotency');
    expect(hits[0]?.lessonId).toBe('idempotency-keys');
  });
  it('searches inside lesson text, not only titles', () => {
    expect(searchContent(index, 'fingerprint').map((h) => h.lessonId)).toContain('idempotency-keys');
  });
  it('finds planned lessons by title', () => {
    const hits = searchContent(index, 'reconciliation');
    expect(hits.find((h) => h.lessonId === 'reconciliation-for-testers')?.planned).toBe(true);
  });
  it('requires every word and ignores one-letter noise', () => {
    expect(searchContent(index, 'idempotency zebra')).toEqual([]);
    expect(searchContent(index, 'a')).toEqual([]);
  });
});
