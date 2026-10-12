/**
 * Scrolls to a lesson section or exercise by element id, opening it first if it sits inside
 * a collapsed <details>, and highlights it briefly so the eye finds it.
 */
export function focusElement(id: string): boolean {
  const target = document.getElementById(id);
  if (!target) return false;
  for (let node: HTMLElement | null = target; node; node = node.parentElement) {
    if (node instanceof HTMLDetailsElement) node.open = true;
  }
  target.querySelectorAll('details').forEach((details) => {
    if (details.parentElement === target) details.open = true;
  });
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  keepAligned(target);
  target.classList.add('is-focused');
  window.setTimeout(() => target.classList.remove('is-focused'), 2400);
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
  return true;
}

/** How long content above the target may keep growing (diagrams rendering) before we stop following. */
export const SETTLE_MS = 4000;
const READER_INPUT = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const;

/**
 * Content above the target can still change height after the scroll - diagrams render
 * asynchronously, the first time from a lazily loaded chunk - and push the target out of view.
 * Re-align it whenever the page's height changes, until the layout settles or the reader takes
 * over by scrolling, tapping or pressing a key.
 */
function keepAligned(target: HTMLElement) {
  if (typeof ResizeObserver === 'undefined') return;
  let lastHeight = document.body.scrollHeight;
  const observer = new ResizeObserver(() => {
    const height = document.body.scrollHeight;
    if (height === lastHeight) return;
    lastHeight = height;
    target.scrollIntoView({ block: 'start' });
  });
  const stop = () => {
    observer.disconnect();
    window.clearTimeout(timer);
    READER_INPUT.forEach((type) => window.removeEventListener(type, stop));
  };
  const timer = window.setTimeout(stop, SETTLE_MS);
  READER_INPUT.forEach((type) => window.addEventListener(type, stop, { passive: true }));
  observer.observe(document.body);
}
