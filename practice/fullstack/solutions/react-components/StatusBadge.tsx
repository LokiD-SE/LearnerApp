import { useId, type ReactElement, type ReactNode } from 'react';
import type { OrderStatus } from './orders.js';

export interface StatusBadgeProps {
  status: OrderStatus;
}

const labels: Record<OrderStatus, string> = {
  PENDING: 'Pending',
  SUCCEEDED: 'Paid',
  FAILED: 'Failed',
  REFUNDED: 'Refunded',
};

/** The status as text a person understands; the class is only for colour. */
export function StatusBadge({ status }: StatusBadgeProps): ReactElement {
  return <span className={`badge badge-${status.toLowerCase()}`}>{labels[status]}</span>;
}

export interface PanelProps {
  title: string;
  children: ReactNode;
}

/** A section named by its own heading; the content is whatever the parent nests inside. */
export function Panel({ title, children }: PanelProps): ReactElement {
  const headingId = useId();
  return (
    <section className="panel" aria-labelledby={headingId}>
      <h2 id={headingId}>{title}</h2>
      {children}
    </section>
  );
}
