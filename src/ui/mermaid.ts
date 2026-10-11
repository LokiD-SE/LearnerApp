/**
 * Mermaid is large, so it is loaded only when a page has a diagram, from the app's own
 * bundle (no CDN), and rendered in strict security mode.
 */
type MermaidApi = typeof import('mermaid').default;

let mermaidPromise: Promise<MermaidApi> | undefined;
let counter = 0;

function loadMermaid(): Promise<MermaidApi> {
  mermaidPromise ??= import('mermaid').then(({ default: mermaid }) => {
    const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: dark ? 'dark' : 'default' });
    return mermaid;
  });
  return mermaidPromise;
}

/** Renders every not-yet-rendered `.diagram` placeholder inside root. */
export async function renderDiagrams(root: HTMLElement): Promise<void> {
  const placeholders = [...root.querySelectorAll<HTMLElement>('.diagram:not([data-rendered])')];
  if (placeholders.length === 0) return;
  let mermaid: MermaidApi;
  try {
    mermaid = await loadMermaid();
  } catch {
    placeholders.forEach((el) => el.setAttribute('data-rendered', 'error'));
    return;
  }
  for (const el of placeholders) {
    const source = el.querySelector('.diagram-source')?.textContent ?? '';
    el.setAttribute('data-rendered', 'pending');
    try {
      counter += 1;
      const { svg } = await mermaid.render(`diagram-${counter}`, source);
      el.innerHTML = svg;
      el.setAttribute('data-rendered', 'ok');
      el.prepend(sizeToggle(el));
    } catch {
      // Keep the source visible: a diagram that fails to render is still readable as text.
      el.setAttribute('data-rendered', 'error');
    }
  }
}

/** Small screens fit the diagram to the width; this switches to its natural size (scrollable). */
function sizeToggle(diagram: HTMLElement): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'diagram-toggle';
  button.textContent = 'Full size';
  button.setAttribute('aria-pressed', 'false');
  button.addEventListener('click', () => {
    const full = diagram.classList.toggle('diagram--full');
    button.setAttribute('aria-pressed', String(full));
    button.textContent = full ? 'Fit to width' : 'Full size';
  });
  return button;
}
