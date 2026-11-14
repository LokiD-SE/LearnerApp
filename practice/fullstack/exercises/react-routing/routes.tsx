// Routes of the SandPay merchant dashboard (fictional), in React Router's data mode.
//
// The components are complete. Write createRoutes and RouteError (below) so that:
//  - "/" renders Layout, with Home as its index route;
//  - "/orders" renders OrdersPage with the orders from api.listOrders(request.signal), loaded by a loader;
//  - "/orders/:orderId" renders OrderDetail with api.getOrder(orderId, request.signal); when that resolves
//    to null, the loader throws data('Order not found', { status: 404 });
//  - an error inside /orders/... renders RouteError *inside* the Layout (the navigation stays visible),
//    and any other URL renders NotFound inside the Layout;
//  - RouteError shows "404 Order not found" (status, then the thrown data) for a thrown data() response,
//    and "Something went wrong. Try again." for anything else - both in a role="alert" element.
import { Link, Outlet, useLoaderData, useNavigation, type RouteObject } from 'react-router';
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
  // TODO: read the error with useRouteError and tell a route error response apart with isRouteErrorResponse.
  return <p role="alert">Something went wrong. Try again.</p>;
}

export function createRoutes(api: OrdersApi): RouteObject[] {
  // TODO: nest the routes under the Layout, load data in loaders and add the error boundaries.
  void api;
  return [{ path: '/', Component: Layout, children: [{ index: true, Component: Home }] }];
}
