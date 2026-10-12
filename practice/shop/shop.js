/*
 * SandPay Demo Shop - a practice target for UI automation (Selenium, Playwright, ...).
 *
 * Everything is fictional and runs in the browser: no server, no real payments. State lives in
 * sessionStorage, so every new browser session starts with an empty cart.
 *
 * The shop deliberately behaves like real web apps that are awkward to automate:
 * - products load asynchronously, and sorting re-renders the list (stale elements);
 * - element ids and one CSS class are generated per page load (brittle locators);
 * - "Add to cart" updates the cart count after a delay, with a toast;
 * - card details are entered in a SandPay iframe;
 * - a processing overlay covers the page while a payment runs (intercepted clicks);
 * - some payments end PENDING and settle later on the order page (asynchronous status).
 * Stable `data-testid` attributes are provided as the recommended test hooks.
 */
'use strict';

const PRODUCTS = [
  { sku: 'espresso-beans', name: 'Espresso beans 1 kg', price: 1899, featured: 1 },
  { sku: 'oat-milk', name: 'Oat milk 1 L', price: 249, featured: 4 },
  { sku: 'pour-over-kit', name: 'Pour-over kit', price: 3450, featured: 2 },
  { sku: 'ceramic-mug', name: 'Ceramic mug', price: 1200, featured: 5 },
  { sku: 'hand-grinder', name: 'Hand grinder', price: 5990, featured: 3 },
  { sku: 'filter-papers', name: 'Filter papers (100)', price: 499, featured: 6 },
];

/** Test cards: the SandPay iframe accepts these codes instead of card numbers. */
const TEST_CARDS = {
  'sandpay-success': { delay: 1500, outcome: 'SUCCEEDED' },
  'sandpay-slow': { delay: 4000, outcome: 'SUCCEEDED' },
  'sandpay-insufficient-funds': {
    delay: 1000,
    decline: 'Payment declined: insufficient funds. Try another card.',
  },
  'sandpay-card-declined': { delay: 1000, decline: 'Payment declined by the card issuer.' },
  'sandpay-unknown': { delay: 2000, outcome: 'PENDING', settlesAs: 'SUCCEEDED', settleAfter: 3000 },
  'sandpay-pending-then-failed': { delay: 2000, outcome: 'PENDING', settlesAs: 'FAILED', settleAfter: 3000 },
};

const money = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' });
const formatMoney = (minor) => money.format(minor / 100);
const randomId = (length = 6) =>
  Array.from(crypto.getRandomValues(new Uint8Array(length)), (b) => (b % 36).toString(36)).join('');
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/* ------------------------------------------------------------------ state */

const store = {
  read(key, fallback) {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  },
  write(key, value) {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable - the shop still works for this page */
    }
  },
};

const cart = {
  lines: () => store.read('sandpay-shop-cart', []),
  save: (lines) =>
    store.write(
      'sandpay-shop-cart',
      lines.filter((l) => l.quantity > 0),
    ),
  count: () => cart.lines().reduce((sum, l) => sum + l.quantity, 0),
  add(sku) {
    const lines = cart.lines();
    const line = lines.find((l) => l.sku === sku);
    if (line) line.quantity += 1;
    else lines.push({ sku, quantity: 1 });
    cart.save(lines);
  },
  change(sku, delta) {
    cart.save(cart.lines().map((l) => (l.sku === sku ? { ...l, quantity: l.quantity + delta } : l)));
  },
  clear: () => cart.save([]),
  detailed: () =>
    cart.lines().flatMap((l) => {
      const product = PRODUCTS.find((p) => p.sku === l.sku);
      return product ? [{ ...product, quantity: l.quantity, total: product.price * l.quantity }] : [];
    }),
  total: () => cart.detailed().reduce((sum, l) => sum + l.total, 0),
};

const orders = {
  get: (id) => store.read('sandpay-shop-orders', {})[id],
  save(order) {
    const all = store.read('sandpay-shop-orders', {});
    all[order.id] = order;
    store.write('sandpay-shop-orders', all);
  },
};

/* ------------------------------------------------------------------ shared UI */

function renderCartCount() {
  const badge = document.querySelector('[data-testid="cart-count"]');
  if (badge) badge.textContent = String(cart.count());
}

function showToast(text) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.setAttribute('role', 'status');
  toast.dataset.testid = 'toast';
  toast.textContent = text;
  document.body.append(toast);
  setTimeout(() => toast.remove(), 2500);
}

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === 'dataset') Object.assign(node.dataset, value);
    else if (name in node && typeof value !== 'string') node[name] = value;
    else node.setAttribute(name, value);
  }
  node.append(...children);
  return node;
}

/* ------------------------------------------------------------------ catalog */

async function initCatalog() {
  const list = document.querySelector('[data-testid="product-list"]');
  const sort = document.querySelector('[data-testid="sort"]');
  // A class name that changes on every load, like the hashed names of CSS-in-JS libraries.
  const hashedCardClass = `card-${randomId(5)}`;

  const render = (order) => {
    const sorted = [...PRODUCTS].sort((a, b) =>
      order === 'price-asc'
        ? a.price - b.price
        : order === 'price-desc'
          ? b.price - a.price
          : a.featured - b.featured,
    );
    list.replaceChildren(
      ...sorted.map((product) => {
        const button = el(
          'button',
          { type: 'button', id: `btn-${randomId()}`, dataset: { testid: `add-to-cart-${product.sku}` } },
          'Add to cart',
        );
        button.addEventListener('click', async () => {
          button.disabled = true;
          button.textContent = 'Adding...';
          await sleep(500); // the "API call"
          cart.add(product.sku);
          renderCartCount();
          button.disabled = false;
          button.textContent = 'Add to cart';
          showToast(`${product.name} added to your cart`);
        });
        return el(
          'li',
          {
            class: `product-card ${hashedCardClass}`,
            id: `product-${randomId()}`,
            dataset: { testid: 'product-card', sku: product.sku },
          },
          el('h2', { dataset: { testid: 'product-name' } }, product.name),
          el(
            'p',
            { class: 'price', dataset: { testid: 'product-price', amountMinor: String(product.price) } },
            formatMoney(product.price),
          ),
          button,
        );
      }),
    );
  };

  list.replaceChildren(
    ...Array.from({ length: 3 }, () => el('li', { class: 'skeleton', 'aria-hidden': 'true' })),
  );
  list.setAttribute('aria-busy', 'true');
  await sleep(800); // products "load" from the server
  render(sort.value);
  list.setAttribute('aria-busy', 'false');

  sort.addEventListener('change', async () => {
    list.setAttribute('aria-busy', 'true');
    await sleep(300);
    render(sort.value);
    list.setAttribute('aria-busy', 'false');
  });
}

/* ------------------------------------------------------------------ cart */

function initCart() {
  const body = document.querySelector('[data-testid="cart-lines"]');
  const empty = document.querySelector('[data-testid="cart-empty"]');
  const content = document.querySelector('[data-testid="cart-content"]');
  const total = document.querySelector('[data-testid="cart-total"]');

  const render = () => {
    const lines = cart.detailed();
    empty.hidden = lines.length > 0;
    content.hidden = lines.length === 0;
    body.replaceChildren(
      ...lines.map((line) => {
        const change = (delta, label, testid) => {
          const button = el(
            'button',
            {
              type: 'button',
              class: 'secondary',
              'aria-label': `${label} ${line.name}`,
              dataset: { testid },
            },
            delta > 0 ? '+' : '-',
          );
          button.addEventListener('click', async () => {
            button.disabled = true;
            await sleep(400); // the cart is "saved on the server"
            cart.change(line.sku, delta);
            render();
            renderCartCount();
          });
          return button;
        };
        const remove = el(
          'button',
          { type: 'button', class: 'secondary', dataset: { testid: 'remove' } },
          'Remove',
        );
        remove.addEventListener('click', async () => {
          remove.disabled = true;
          await sleep(400);
          cart.change(line.sku, -line.quantity);
          render();
          renderCartCount();
        });
        return el(
          'tr',
          { dataset: { testid: 'cart-line', sku: line.sku } },
          el('td', { dataset: { testid: 'line-name' } }, line.name),
          el(
            'td',
            {},
            el(
              'span',
              { class: 'qty' },
              change(-1, 'One fewer', 'decrease'),
              el('span', { dataset: { testid: 'line-quantity' } }, String(line.quantity)),
              change(1, 'One more', 'increase'),
            ),
          ),
          el(
            'td',
            { class: 'num', dataset: { testid: 'line-total', amountMinor: String(line.total) } },
            formatMoney(line.total),
          ),
          el('td', {}, remove),
        );
      }),
    );
    total.textContent = formatMoney(cart.total());
    total.dataset.amountMinor = String(cart.total());
  };
  render();
}

/* ------------------------------------------------------------------ checkout */

function initCheckout() {
  const lines = cart.detailed();
  const form = document.querySelector('[data-testid="checkout-form"]');
  const empty = document.querySelector('[data-testid="checkout-empty"]');
  if (lines.length === 0) {
    form.hidden = true;
    empty.hidden = false;
    return;
  }
  document
    .querySelector('[data-testid="summary-lines"]')
    .replaceChildren(
      ...lines.map((line) => el('li', {}, `${line.quantity} × ${line.name} - ${formatMoney(line.total)}`)),
    );
  const total = cart.total();
  const totalNode = document.querySelector('[data-testid="order-total"]');
  totalNode.textContent = formatMoney(total);
  totalNode.dataset.amountMinor = String(total);

  const email = document.querySelector('[data-testid="email"]');
  const pay = document.querySelector('[data-testid="pay-button"]');
  const error = document.querySelector('[data-testid="payment-error"]');
  const overlay = document.querySelector('[data-testid="processing-overlay"]');
  pay.textContent = `Pay ${formatMoney(total)}`;

  let card = null;
  const update = () => {
    pay.disabled = !(card && email.validity.valid && email.value.trim());
  };
  email.addEventListener('input', update);
  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin || event.data?.type !== 'sandpay:card') return;
    card = event.data.ready ? event.data.card : null;
    update();
  });

  pay.addEventListener('click', async () => {
    if (pay.disabled || !card) return;
    const testCard = TEST_CARDS[card];
    error.textContent = '';
    pay.disabled = true;
    overlay.hidden = false;
    await sleep(testCard.delay);
    if (testCard.decline) {
      overlay.hidden = true;
      error.textContent = testCard.decline;
      update();
      return;
    }
    const id = `ord_${randomId(8)}`;
    orders.save({
      id,
      email: email.value.trim(),
      total,
      lines: lines.map(({ sku, name, quantity, total: lineTotal }) => ({
        sku,
        name,
        quantity,
        total: lineTotal,
      })),
      status: testCard.outcome,
      settlesAs: testCard.settlesAs ?? null,
      settlesAt: testCard.settleAfter ? Date.now() + testCard.settleAfter : null,
    });
    cart.clear();
    window.location.assign(`order.html?id=${encodeURIComponent(id)}`);
  });
  update();
}

/* ------------------------------------------------------------------ order */

function initOrder() {
  const id = new URLSearchParams(window.location.search).get('id');
  const found = document.querySelector('[data-testid="order-found"]');
  const missing = document.querySelector('[data-testid="order-missing"]');
  const order = id ? orders.get(id) : undefined;
  if (!order) {
    found.hidden = true;
    missing.hidden = false;
    return;
  }
  document.querySelector('[data-testid="order-id"]').textContent = order.id;
  const total = document.querySelector('[data-testid="order-total"]');
  total.textContent = formatMoney(order.total);
  total.dataset.amountMinor = String(order.total);

  const status = document.querySelector('[data-testid="order-status"]');
  const message = document.querySelector('[data-testid="order-message"]');
  const MESSAGES = {
    SUCCEEDED: 'Payment received - thank you. A receipt is on its way.',
    PENDING: 'We are waiting for SandPay to confirm your payment. This page updates by itself.',
    FAILED: 'The payment failed after all. You have not been charged; please try again.',
  };
  const render = (current) => {
    status.textContent = current.status;
    status.className = `status status-${current.status}`;
    message.textContent = MESSAGES[current.status];
  };
  render(order);

  if (order.status === 'PENDING') {
    const poll = setInterval(() => {
      const latest = orders.get(order.id);
      if (latest.status === 'PENDING' && Date.now() >= latest.settlesAt) {
        latest.status = latest.settlesAs;
        orders.save(latest);
      }
      render(latest);
      if (latest.status !== 'PENDING') clearInterval(poll);
    }, 1000);
  }
}

/* ------------------------------------------------------------------ start */

renderCartCount();
({ catalog: initCatalog, cart: initCart, checkout: initCheckout, order: initOrder })[
  document.body.dataset.page
]?.();
