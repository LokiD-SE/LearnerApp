// A customer comment on a SandPay order, shown in the merchant dashboard - reference solution.
// React escapes text children, so rendering the text as text is the whole XSS fix for the body; the link
// needs an allow-list of URL schemes, because React 19 blocks only javascript: URLs.

export interface Comment {
  author: string;
  text: string;
  website?: string;
}

const ALLOWED_SCHEMES = new Set(['http:', 'https:', 'mailto:']);

export function safeHref(raw: string): string | undefined {
  const value = raw.trim();
  // A path on this site: one leading slash. '//host' would be another site with our scheme.
  if (value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\')) return value;
  try {
    const url = new URL(value);
    return ALLOWED_SCHEMES.has(url.protocol) ? url.href : undefined;
  } catch {
    return undefined; // not an absolute URL
  }
}

export function CommentView({ comment }: { comment: Comment }) {
  const href = comment.website === undefined ? undefined : safeHref(comment.website);
  return (
    <article aria-label={`Comment from ${comment.author}`}>
      <p>{comment.author}</p>
      <div style={{ whiteSpace: 'pre-line' }}>{comment.text}</div>
      {href && (
        <a href={href} rel="nofollow ugc noopener noreferrer">
          Website
        </a>
      )}
    </article>
  );
}
