import { useEffect, useRef } from 'preact/hooks';
import { renderMarkdown } from '../markdown';
import { renderDiagrams } from '../mermaid';

export function Markdown({
  source,
  inline = false,
  class: className,
}: {
  source: string;
  inline?: boolean;
  class?: string;
}) {
  const ref = useRef<HTMLDivElement & HTMLSpanElement>(null);
  const html = renderMarkdown(source, inline);
  useEffect(() => {
    if (ref.current && html.includes('class="diagram"')) void renderDiagrams(ref.current);
  }, [html]);
  if (inline) return <span ref={ref} class={className} dangerouslySetInnerHTML={{ __html: html }} />;
  return (
    <div
      ref={ref}
      class={['prose', className].filter(Boolean).join(' ')}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
