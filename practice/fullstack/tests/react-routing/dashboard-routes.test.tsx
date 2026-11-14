// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { createRoutes } from '../../exercises/react-routing/routes.js';
import type { Order, OrdersApi } from '../../exercises/react-routing/orders-api.js';

const orders: Order[] = [
  { id: 'ORD-1001', customer: 'Asha Rao', amountMinor: 125000, currency: 'INR', status: 'SUCCEEDED' },
  { id: 'ORD-1002', customer: 'Lukas Weber', amountMinor: 4999, currency: 'EUR', status: 'PENDING' },
];

/** A fake API that records each call and the AbortSignal it was given. */
function fakeApi(list: Order[] = orders, overrides: Partial<OrdersApi> = {}) {
  const calls: { method: string; arg?: string; signal: AbortSignal }[] = [];
  const api: OrdersApi = {
    async listOrders(signal) {
      calls.push({ method: 'listOrders', signal });
      return list;
    },
    async getOrder(orderId, signal) {
      calls.push({ method: 'getOrder', arg: orderId, signal });
      return list.find((order) => order.id === orderId) ?? null;
    },
    ...overrides,
  };
  return { api, calls };
}

function renderAt(url: string, api: OrdersApi) {
  const router = createMemoryRouter(createRoutes(api), { initialEntries: [url] });
  render(<RouterProvider router={router} />);
  return router;
}

const dashboardNav = () => screen.getByRole('navigation', { name: 'Dashboard' });

describe('dashboard routes', { tags: ['@exercise'] }, () => {
  it('renders the layout with the home page at /', async () => {
    renderAt('/', fakeApi().api);
    expect(await screen.findByRole('heading', { name: 'SandPay dashboard' })).toBeTruthy();
    expect(within(dashboardNav()).getByRole('link', { name: 'Orders' })).toBeTruthy();
  });

  it('loads the order list with a loader that passes the request signal', async () => {
    const { api, calls } = fakeApi();
    renderAt('/orders', api);
    expect(await screen.findByRole('link', { name: 'ORD-1001' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'ORD-1002' })).toBeTruthy();
    expect(calls.map((c) => c.method)).toEqual(['listOrders']);
    expect(calls[0]?.signal).toBeInstanceOf(AbortSignal);
    // The layout is still there around the page.
    expect(dashboardNav()).toBeTruthy();
  });

  it('shows the empty state when there are no orders', async () => {
    renderAt('/orders', fakeApi([]).api);
    expect(await screen.findByText('No orders yet.')).toBeTruthy();
  });

  it('reads :orderId from the URL and shows that order', async () => {
    const { api, calls } = fakeApi();
    renderAt('/orders/ORD-1002', api);
    expect(await screen.findByRole('heading', { name: 'Order ORD-1002' })).toBeTruthy();
    expect(screen.getByText('Amount: EUR 49.99')).toBeTruthy();
    expect(calls).toMatchObject([{ method: 'getOrder', arg: 'ORD-1002' }]);
    expect(calls[0]?.signal).toBeInstanceOf(AbortSignal);
  });

  it('navigates from the list to an order and back by clicking links', async () => {
    const user = userEvent.setup();
    const router = renderAt('/orders', fakeApi().api);
    await user.click(await screen.findByRole('link', { name: 'ORD-1001' }));
    expect(await screen.findByRole('heading', { name: 'Order ORD-1001' })).toBeTruthy();
    expect(router.state.location.pathname).toBe('/orders/ORD-1001');
    await user.click(screen.getByRole('link', { name: 'Back to orders' }));
    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeTruthy();
  });

  it('shows "404 Order not found" inside the layout for an unknown order', async () => {
    renderAt('/orders/ORD-9999', fakeApi().api);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('404 Order not found');
    // The error boundary is nested, so the navigation is still usable.
    expect(within(dashboardNav()).getByRole('link', { name: 'Home' })).toBeTruthy();
  });

  it('shows a generic error, inside the layout, when the API fails', async () => {
    const { api } = fakeApi(orders, {
      listOrders: async () => {
        throw new Error('503 from the API');
      },
    });
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    renderAt('/orders', api);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Something went wrong. Try again.');
    expect(dashboardNav()).toBeTruthy();
    spy.mockRestore();
    warn.mockRestore();
  });

  it('renders "Page not found" inside the layout for any other URL', async () => {
    renderAt('/settings/payouts', fakeApi().api);
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeTruthy();
    expect(dashboardNav()).toBeTruthy();
  });
});
