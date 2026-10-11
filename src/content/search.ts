/**
 * Plain full-text search over the bundled content: lesson titles, summaries, concepts,
 * section text and exercises, plus planned lessons by title. No index server needed.
 */
import type { ContentIndex } from './validate';

export interface SearchHit {
  lessonId: string;
  title: string;
  planned: boolean;
  score: number;
  /** where the best match was found */
  where: string;
  /** a short excerpt around the first match, plain text */
  excerpt: string;
}

const plain = (markdown: string) =>
  markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[`*_>#|[\]()-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

function excerpt(text: string, term: string): string {
  const at = text.toLowerCase().indexOf(term);
  if (at < 0) return text.slice(0, 140);
  const start = Math.max(0, at - 60);
  const end = Math.min(text.length, at + term.length + 80);
  return `${start > 0 ? '…' : ''}${text.slice(start, end)}${end < text.length ? '…' : ''}`;
}

export function searchContent(index: ContentIndex, query: string): SearchHit[] {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length >= 2);
  if (terms.length === 0) return [];
  const first = terms[0]!;
  const hits: SearchHit[] = [];

  for (const ref of index.refs.values()) {
    const lesson = index.lessons.get(ref.id);
    const fields: { where: string; text: string; weight: number }[] = [
      { where: 'Title', text: ref.title, weight: 6 },
      { where: 'Summary', text: ref.summary, weight: 3 },
    ];
    if (lesson) {
      fields.push({
        where: 'Concepts',
        text: lesson.concepts.map((c) => `${c.name} ${c.summary}`).join(' '),
        weight: 4,
      });
      fields.push({ where: 'Tags', text: lesson.tags.join(' '), weight: 3 });
      for (const section of lesson.sections)
        fields.push({ where: section.title, text: plain(section.body), weight: 1 });
      for (const exercise of lesson.exercises) {
        fields.push({
          where: `Exercise: ${exercise.title}`,
          text: plain(`${exercise.title} ${exercise.prompt}`),
          weight: 1,
        });
      }
    }
    let score = 0;
    let best: { where: string; text: string; weight: number } | undefined;
    for (const field of fields) {
      const lower = field.text.toLowerCase();
      const matched = terms.filter((term) => lower.includes(term)).length;
      if (matched === 0) continue;
      score += matched * field.weight;
      if (!best || field.weight > best.weight) best = field;
    }
    // Every term must appear somewhere in the lesson.
    const all = fields.map((f) => f.text.toLowerCase()).join(' ');
    if (score > 0 && best && terms.every((term) => all.includes(term))) {
      hits.push({
        lessonId: ref.id,
        title: ref.title,
        planned: ref.planned,
        score,
        where: best.where,
        excerpt: excerpt(best.text, first),
      });
    }
  }
  return hits.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
}
