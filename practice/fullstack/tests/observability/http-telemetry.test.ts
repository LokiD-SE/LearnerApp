import express, { type Express } from 'express';
import request from 'supertest';
import { Histogram, telemetry } from '../../exercises/observability/http-telemetry.js';

const TRACE_ID = '4bf92f3577b34da6a3ce929d0e0e4736';
const INCOMING = `00-${TRACE_ID}-00f067aa0ba902b7-01`;
const SPAN_ID = 'b7ad6b7169203331';
const NEW_TRACE_ID = '0af7651916cd43dd8448eb211c80319c';

interface Rig {
  app: Express;
  logs: Record<string, unknown>[];
  histogram: Histogram;
}

/** An app with the telemetry middleware first and a fake clock: each handler "takes" a set time. */
function rig(): Rig {
  const logs: Record<string, unknown>[] = [];
  const histogram = new Histogram(
    'http_server_request_duration_seconds',
    'Duration of HTTP server requests.',
  );
  let clock = 1000;
  const app = express();
  app.use(
    telemetry({
      log: (record) => logs.push(record),
      histogram,
      now: () => clock,
      wallClock: () => new Date('2026-11-14T09:30:00.000Z'),
      newSpanId: () => SPAN_ID,
      newTraceId: () => NEW_TRACE_ID,
    }),
  );
  app.get('/merchants/:merchantId/orders', (req, res) => {
    clock += 42;
    res.json({ merchantId: req.params.merchantId, trace: res.locals.trace });
  });
  const payments = express.Router();
  payments.get('/payments/:paymentId', (req, res) => {
    clock += 7;
    res.json({ id: req.params.paymentId });
  });
  app.use('/api', payments);
  app.get('/slow-float', (req, res) => {
    clock += 12.3456789;
    res.json({});
  });
  app.get('/ledger', (req, res) => {
    clock += 1200;
    res.status(503).json({ error: 'ledger_unavailable' });
  });
  app.use((req, res) => {
    clock += 1;
    res.status(404).json({ error: 'not_found' });
  });
  return { app, logs, histogram };
}

describe('telemetry - trace context and logs', { tags: ['@exercise'] }, () => {
  test('joins the incoming trace and shares the context with handlers', async () => {
    const { app } = rig();
    const res = await request(app).get('/merchants/m_42/orders').set('traceparent', INCOMING);
    expect(res.body.trace).toEqual({ traceId: TRACE_ID, parentId: SPAN_ID, sampled: true });
  });

  test('logs one structured record per request with the route template and trace ids', async () => {
    const { app, logs } = rig();
    await request(app).get('/merchants/m_42/orders?token=secret-value').set('traceparent', INCOMING);
    expect(logs).toEqual([
      {
        time: '2026-11-14T09:30:00.000Z',
        level: 'info',
        msg: 'request completed',
        trace_id: TRACE_ID,
        span_id: SPAN_ID,
        'http.request.method': 'GET',
        'http.route': '/merchants/:merchantId/orders',
        'url.path': '/merchants/m_42/orders',
        'http.response.status_code': 200,
        duration_ms: 42,
      },
    ]);
    expect(JSON.stringify(logs)).not.toContain('secret-value');
  });

  test('starts a new trace when there is no traceparent', async () => {
    const { app, logs } = rig();
    await request(app).get('/api/payments/pay_7');
    expect(logs[0]).toMatchObject({
      trace_id: NEW_TRACE_ID,
      span_id: SPAN_ID,
      'http.route': '/api/payments/:paymentId',
    });
  });

  test('marks a 5xx as an error with error.type', async () => {
    const { app, logs } = rig();
    await request(app).get('/ledger');
    expect(logs[0]).toMatchObject({
      level: 'error',
      'http.response.status_code': 503,
      'error.type': '503',
      duration_ms: 1200,
    });
  });

  test('leaves http.route and error.type out when nothing matched and nothing failed', async () => {
    const { app, logs } = rig();
    await request(app).get('/no/such/page');
    expect(logs[0]).toMatchObject({
      level: 'info',
      'url.path': '/no/such/page',
      'http.response.status_code': 404,
    });
    expect(logs[0]).not.toHaveProperty('http.route');
    expect(logs[0]).not.toHaveProperty('error.type');
  });

  test('rounds duration_ms to 3 decimals', async () => {
    const { app, logs } = rig();
    await request(app).get('/slow-float');
    expect(logs[0]).toMatchObject({ duration_ms: 12.346 });
  });

  test('records an unknown method as _OTHER', async () => {
    const { app, logs } = rig();
    await request(app).propfind('/merchants/m_42/orders');
    expect(logs[0]).toMatchObject({ 'http.request.method': '_OTHER' });
  });
});

describe('telemetry - the duration histogram', { tags: ['@exercise'] }, () => {
  test('one series per route template, not per URL', async () => {
    const { app, histogram } = rig();
    for (const merchant of ['m_1', 'm_2', 'm_3', 'm_4'])
      await request(app).get(`/merchants/${merchant}/orders`);
    expect(histogram.seriesCount()).toBe(1);
  });

  test('renders the Prometheus text format with cumulative buckets in seconds', async () => {
    const { app, histogram } = rig();
    await request(app).get('/merchants/m_1/orders');
    await request(app).get('/merchants/m_2/orders');
    await request(app).get('/ledger');
    const text = histogram.render();
    const lines = text.trimEnd().split('\n');
    expect(lines.slice(0, 2)).toEqual([
      '# HELP http_server_request_duration_seconds Duration of HTTP server requests.',
      '# TYPE http_server_request_duration_seconds histogram',
    ]);
    const ledger = 'http_request_method="GET",http_response_status_code="503",http_route="/ledger"';
    const orders =
      'http_request_method="GET",http_response_status_code="200",http_route="/merchants/:merchantId/orders"';
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${orders},le="0.025"} 0`);
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${orders},le="0.05"} 2`);
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${orders},le="10"} 2`);
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${orders},le="+Inf"} 2`);
    expect(lines).toContain(`http_server_request_duration_seconds_sum{${orders}} 0.084`);
    expect(lines).toContain(`http_server_request_duration_seconds_count{${orders}} 2`);
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${ledger},le="1"} 0`);
    expect(lines).toContain(`http_server_request_duration_seconds_bucket{${ledger},le="2.5"} 1`);
    expect(lines).toContain(`http_server_request_duration_seconds_count{${ledger}} 1`);
    expect(lines).toHaveLength(2 + 2 * (15 + 2));
  });
});

describe('Histogram', { tags: ['@exercise'] }, () => {
  test('counts a value equal to a bound in that bucket (le is "less than or equal")', () => {
    const h = new Histogram('job_duration_seconds', 'Job duration.', [0.1, 1]);
    h.observe({}, 0.1);
    h.observe({}, 1.5);
    expect(h.render()).toBe(
      [
        '# HELP job_duration_seconds Job duration.',
        '# TYPE job_duration_seconds histogram',
        'job_duration_seconds_bucket{le="0.1"} 1',
        'job_duration_seconds_bucket{le="1"} 1',
        'job_duration_seconds_bucket{le="+Inf"} 2',
        'job_duration_seconds_sum 1.6',
        'job_duration_seconds_count 2',
        '',
      ].join('\n'),
    );
  });

  test('sorts series and label keys, and escapes label values', () => {
    const h = new Histogram('job_duration_seconds', 'Job duration.', [1]);
    h.observe({ queue: 'b', job: 'refund' }, 0.5);
    h.observe({ queue: 'a "fast"\\lane\nx', job: 'refund' }, 0.5);
    const lines = h.render().split('\n');
    expect(lines[2]).toBe(
      'job_duration_seconds_bucket{job="refund",queue="a \\"fast\\"\\\\lane\\nx",le="1"} 1',
    );
    expect(lines[6]).toBe('job_duration_seconds_bucket{job="refund",queue="b",le="1"} 1');
  });
});
