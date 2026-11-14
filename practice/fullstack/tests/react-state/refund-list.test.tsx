// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { RefundList, type RefundLine } from '../../exercises/react-state/RefundList.js';

// Fictional SandPay Demo Shop products. Frozen, so any mutation of the props throws.
function lines(): readonly RefundLine[] {
  return Object.freeze([
    Object.freeze({ id: 'beans', label: 'Espresso beans', unitMinor: 1250, quantity: 1 }),
    Object.freeze({ id: 'milk', label: 'Oat milk 1 L', unitMinor: 299, quantity: 2 }),
  ]);
}

const quantityText = (label: string) =>
  within(screen.getByRole('listitem', { name: label })).getByText(/ x /);

describe('RefundList', { tags: ['@exercise'] }, () => {
  it('shows each line and the total', () => {
    render(<RefundList initialLines={lines()} />);
    expect(quantityText('Espresso beans').textContent).toBe('Espresso beans x 1');
    expect(screen.getByText(/^Total:/).textContent).toBe('Total: 18.48 EUR');
  });

  it('one more: the quantity and the total change on screen', async () => {
    const user = userEvent.setup();
    render(<RefundList initialLines={lines()} />);
    await user.click(screen.getByRole('button', { name: 'One more Espresso beans' }));
    expect(quantityText('Espresso beans').textContent).toBe('Espresso beans x 2');
    expect(screen.getByText(/^Total:/).textContent).toBe('Total: 30.98 EUR');
  });

  it('add three adds three, not one', async () => {
    const user = userEvent.setup();
    render(<RefundList initialLines={lines()} />);
    await user.click(screen.getByRole('button', { name: 'Add three Oat milk 1 L' }));
    expect(quantityText('Oat milk 1 L').textContent).toBe('Oat milk 1 L x 5');
    expect(screen.getByText(/^Total:/).textContent).toBe('Total: 27.45 EUR');
  });

  it('remove takes the line out and updates the total', async () => {
    const user = userEvent.setup();
    render(<RefundList initialLines={lines()} />);
    await user.click(screen.getByRole('button', { name: 'Remove Espresso beans' }));
    expect(screen.queryByRole('listitem', { name: 'Espresso beans' })).toBeNull();
    expect(screen.getByText(/^Total:/).textContent).toBe('Total: 5.98 EUR');
  });

  it('never changes the lines it was given', async () => {
    const user = userEvent.setup();
    const given = lines();
    const before = JSON.stringify(given);
    render(<RefundList initialLines={given} />);
    await user.click(screen.getByRole('button', { name: 'One more Espresso beans' }));
    await user.click(screen.getByRole('button', { name: 'Add three Oat milk 1 L' }));
    expect(JSON.stringify(given)).toBe(before);
    expect(quantityText('Espresso beans').textContent).toBe('Espresso beans x 2');
  });
});
