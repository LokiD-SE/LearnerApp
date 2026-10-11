/**
 * Markdown -> safe HTML. Content is our own, but raw HTML in it is escaped anyway and the
 * output is sanitised, so a lesson can never inject script. Code blocks are highlighted;
 * ```mermaid blocks become placeholders that the Markdown component renders lazily.
 */
import { Marked, type Tokens } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import http from 'highlight.js/lib/languages/http';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import plaintext from 'highlight.js/lib/languages/plaintext';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';

const languages = { bash, http, java, javascript, json, plaintext, sql, typescript, xml, yaml };
for (const [name, definition] of Object.entries(languages)) hljs.registerLanguage(name, definition);
hljs.registerAliases(['sh', 'shell', 'curl'], { languageName: 'bash' });
hljs.registerAliases(['html'], { languageName: 'xml' });
hljs.registerAliases(['js'], { languageName: 'javascript' });
hljs.registerAliases(['ts'], { languageName: 'typescript' });

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

export function highlight(code: string, language: string | undefined): string {
  const lang = language && hljs.getLanguage(language) ? language : 'plaintext';
  return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
}

const marked = new Marked({
  gfm: true,
  breaks: false,
  renderer: {
    code({ text, lang }: Tokens.Code) {
      const language = (lang ?? '').trim().split(/\s+/)[0] ?? '';
      if (language === 'mermaid') {
        // The source travels as escaped text (sanitisers rightly strip attribute values
        // containing "-->", and Mermaid arrows contain exactly that).
        return `<div class="diagram"><pre class="diagram-source">${escapeHtml(text)}</pre></div>`;
      }
      const label = language ? `<span class="code-lang">${escapeHtml(language)}</span>` : '';
      return `<div class="code-block">${label}<pre><code class="hljs">${highlight(text, language || undefined)}</code></pre></div>`;
    },
    html({ text }: Tokens.HTML | Tokens.Tag) {
      return escapeHtml(text);
    },
    link({ href, title, tokens }: Tokens.Link) {
      const inner = this.parser.parseInline(tokens);
      const external = /^https?:\/\//.test(href);
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
      const target = external ? ' target="_blank" rel="noopener noreferrer"' : '';
      return `<a href="${escapeHtml(href)}"${titleAttr}${target}>${inner}</a>`;
    },
    table(token: Tokens.Table) {
      // Wide tables scroll inside their own box instead of widening the page on phones.
      const header = token.header.map((cell) => `<th>${this.parser.parseInline(cell.tokens)}</th>`).join('');
      const rows = token.rows
        .map(
          (row) =>
            `<tr>${row.map((cell) => `<td>${this.parser.parseInline(cell.tokens)}</td>`).join('')}</tr>`,
        )
        .join('');
      return `<div class="table-scroll"><table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
    },
  },
});

const cache = new Map<string, string>();

export function renderMarkdown(source: string, inline = false): string {
  const cacheKey = `${inline ? 'i' : 'b'}:${source}`;
  const cached = cache.get(cacheKey);
  if (cached !== undefined) return cached;
  const raw = inline ? (marked.parseInline(source) as string) : (marked.parse(source) as string);
  const safe = DOMPurify.sanitize(raw, { ADD_ATTR: ['target'] });
  cache.set(cacheKey, safe);
  return safe;
}
