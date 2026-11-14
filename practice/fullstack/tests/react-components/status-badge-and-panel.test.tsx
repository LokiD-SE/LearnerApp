// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import { Panel, StatusBadge } from '../../exercises/react-components/StatusBadge.js';
import type { OrderStatus } from '../../exercises/react-components/orders.js';

describe('StatusBadge and Panel', { tags: ['@exercise'] }, () => {
  describe('StatusBadge', () => {
    it.each<[OrderStatus, string]>([
      ['PENDING', 'Pending'],
      ['SUCCEEDED', 'Paid'],
      ['FAILED', 'Failed'],
      ['REFUNDED', 'Refunded'],
    ])('shows %s as the words "%s"', (status, text) => {
      const { container } = render(<StatusBadge status={status} />);
      const badge = container.firstElementChild;
      expect(badge?.tagName).toBe('SPAN');
      expect(badge?.textContent).toBe(text);
    });

    it('has the badge classes for colour', () => {
      const { container } = render(<StatusBadge status="SUCCEEDED" />);
      const badge = container.firstElementChild;
      expect(badge?.classList.contains('badge')).toBe(true);
      expect(badge?.classList.contains('badge-succeeded')).toBe(true);
    });
  });

  describe('Panel', () => {
    it('is a region named by its heading, with the children inside', () => {
      render(
        <Panel title="Recent orders">
          <p>Three orders today</p>
        </Panel>,
      );
      const region = screen.getByRole('region', { name: 'Recent orders' });
      expect(within(region).getByRole('heading', { level: 2, name: 'Recent orders' })).toBeTruthy();
      expect(within(region).getByText('Three orders today')).toBeTruthy();
    });

    it('puts the children after the heading', () => {
      render(
        <Panel title="Refunds">
          <button>Refund</button>
        </Panel>,
      );
      const region = screen.getByRole('region', { name: 'Refunds' });
      const heading = within(region).getByRole('heading');
      const button = within(region).getByRole('button', { name: 'Refund' });
      expect(heading.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('gives two panels on one page different ids, so each keeps its own name', () => {
      render(
        <>
          <Panel title="Payments">
            <p>a</p>
          </Panel>
          <Panel title="Payouts">
            <p>b</p>
          </Panel>
        </>,
      );
      expect(screen.getByRole('region', { name: 'Payments' })).toBeTruthy();
      expect(screen.getByRole('region', { name: 'Payouts' })).toBeTruthy();
    });
  });
});
