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
  target.classList.add('is-focused');
  window.setTimeout(() => target.classList.remove('is-focused'), 2400);
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
  return true;
}
