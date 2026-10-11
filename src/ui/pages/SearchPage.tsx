import { useEffect, useState } from 'preact/hooks';
import { searchContent } from '../../content/search';
import type { ContentIndex } from '../../content/validate';
import { StatusBadge } from '../components/Badges';
import { href } from '../router';

export function SearchPage({ index, query }: { index: ContentIndex; query: string }) {
  const [text, setText] = useState(query);
  useEffect(() => setText(query), [query]);
  const hits = searchContent(index, query);

  return (
    <section class="page narrow">
      <h1 tabIndex={-1}>Search</h1>
      <form
        class="search-form"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          window.location.hash = href.search(text.trim());
        }}
      >
        <label for="search-input" class="sr-only">
          Search lessons
        </label>
        <input
          id="search-input"
          type="search"
          value={text}
          placeholder="e.g. idempotency, refund, timeout"
          onInput={(e) => setText((e.target as HTMLInputElement).value)}
        />
        <button type="submit" class="button primary">
          Search
        </button>
      </form>
      {query.trim().length > 0 && (
        <p class="muted" aria-live="polite">
          {hits.length} {hits.length === 1 ? 'result' : 'results'} for "{query}".
        </p>
      )}
      {query.trim().length > 0 && hits.length === 0 && (
        <div class="empty-state">
          <p>No lessons mention all of those words. Try fewer or different words.</p>
        </div>
      )}
      <ul class="search-results">
        {hits.map((hit) => (
          <li key={hit.lessonId}>
            <a href={href.lesson(hit.lessonId)}>{hit.title}</a>{' '}
            {hit.planned && <StatusBadge status="planned" />}
            <p class="small muted">
              <strong>{hit.where}:</strong> {hit.excerpt}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
