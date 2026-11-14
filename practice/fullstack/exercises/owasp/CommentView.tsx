// A customer comment on a SandPay order, shown in the merchant dashboard. The comment, the author's name and
// the "website" are typed by customers - untrusted input. This first draft renders them as HTML and puts
// the website straight into href.
//
// Fix it:
//   - safeHref(raw) returns a URL that is safe to put in href, or undefined: absolute http:, https: and
//     mailto: URLs, and paths on this site that start with a single '/'. Everything else - javascript:,
//     data:, vbscript:, file:, protocol-relative //host, garbage - is undefined.
//   - CommentView renders the text as text (line breaks kept with CSS), never as HTML, and renders the
//     website as a link only when safeHref accepts it, with rel="nofollow ugc noopener noreferrer".

export interface Comment {
  author: string;
  text: string;
  website?: string;
}

export function safeHref(raw: string): string | undefined {
  return raw;
}

export function CommentView({ comment }: { comment: Comment }) {
  return (
    <article aria-label={`Comment from ${comment.author}`}>
      <p dangerouslySetInnerHTML={{ __html: comment.author }} />
      <div dangerouslySetInnerHTML={{ __html: comment.text }} />
      {comment.website && <a href={comment.website}>Website</a>}
    </article>
  );
}
