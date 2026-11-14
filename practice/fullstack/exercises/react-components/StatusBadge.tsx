import type { ReactElement, ReactNode } from 'react';
import type { OrderStatus } from './orders.js';

export interface StatusBadgeProps {
  status: OrderStatus;
}

/**
 * Exercise 1a. Render the status as a `<span>` whose visible text a person understands:
 *   PENDING -> "Pending", SUCCEEDED -> "Paid", FAILED -> "Failed", REFUNDED -> "Refunded".
 * Give it the class names `badge badge-<status in lower case>` (for example `badge badge-succeeded`),
 * so CSS can colour it - but the meaning must be in the text, never in the colour alone.
 */
export function StatusBadge(_props: StatusBadgeProps): ReactElement {
  throw new Error('TODO: StatusBadge');
}

export interface PanelProps {
  title: string;
  children: ReactNode;
}

/**
 * Exercise 1b. A reusable panel: a `<section>` with an `<h2>` showing `title`, and the `children`
 * after the heading. The section must be named by its heading (aria-labelledby pointing at the
 * heading's id), so it is a named "region" that tests and screen readers can find by title.
 * Two panels on one page must not share an id - `useId()` from React gives a unique one.
 */
export function Panel(_props: PanelProps): ReactElement {
  throw new Error('TODO: Panel');
}
