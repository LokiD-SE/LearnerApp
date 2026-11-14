// Routes of the SandPay merchant dashboard (fictional), in React Router's data mode. Reference solution.
import {
  data,
  isRouteErrorResponse,
  Link,
  Outlet,
  useLoaderData,
  useNavigation,
  useRouteError,
  type RouteObject,
} from 'react-router';
import { formatAmount, type Order, type OrdersApi } from './orders-api.js';

/* ---------------------------------------------------------------- components (complete) */

export function Layout() {
  const navigation = useNavigation();
  return (
    <>
      <header>
        <nav aria-label="Dashboard">
          <Link to="/">Home</Link> <Link to="/orders">Orders</Link>
        </nav>
        {navigation.state === 'loading' && <p role="status">Loading…</p>}
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}

export function Home() {
  return <h1>SandPay dashboard</h1>;
}

export function OrdersPage() {
  const orders = useLoaderData<Order[]>();
  return (
    <section aria-labelledby="orders-heading">
      <h1 id="orders-heading">Orders</h1>
      {orders.length === 0 ? (
        <p>No orders yet.</p>
      ) : (
        <ul>
          {orders.map((order) => (
            <li key={order.id}>
              <Link to={`/orders/${order.id}`}>{order.id}</Link> - {order.customer}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function OrderDetail() {
  const order = useLoaderData<Order>();
  return (
    <article aria-labelledby="order-heading">
      <h1 id="order-heading">Order {order.id}</h1>
      <p>Customer: {order.customer}</p>
      <p>Amount: {formatAmount(order.amountMinor, order.currency)}</p>
      <p>Status: {order.status}</p>
      <Link to="/orders">Back to orders</Link>
    </article>
  );
}

export function NotFound() {
  return <h1>Page not found</h1>;
}

/* ---------------------------------------------------------------- the exercise */

/** Shows a thrown data() response (404 and friends) as a message, anything else as a generic error. */
export function RouteError() {
  const error = useRouteError();
  if (isRouteErrorResponse(error)) {
    return (
      <p role="alert">
        {error.status} {String(error.data)}
      </p>
    );
  }
  return <p role="alert">Something went wrong. Try again.</p>;
}

export function createRoutes(api: OrdersApi): RouteObject[] {
  return [
    {
      path: '/',
      Component: Layout,
      // The last line of defence: an error the routes below don't handle replaces the whole page.
      ErrorBoundary: RouteError,
      children: [
        { index: true, Component: Home },
        {
          path: 'orders',
          // Errors here render inside the Layout's <Outlet />, so the navigation stays usable.
          ErrorBoundary: RouteError,
          children: [
            {
              index: true,
              Component: OrdersPage,
              loader: ({ request }) => api.listOrders(request.signal),
            },
            {
              path: ':orderId',
              Component: OrderDetail,
              loader: async ({ params, request }) => {
                const order = await api.getOrder(params.orderId ?? '', request.signal);
                if (!order) throw data('Order not found', { status: 404 });
                return order;
              },
            },
          ],
        },
        { path: '*', Component: NotFound },
      ],
    },
  ];
}
