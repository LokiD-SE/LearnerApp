import { createContractChecker } from '../../exercises/openapi/contract-checker.js';
import type { OpenApiDocument } from '../../exercises/openapi/oas-ajv.js';

/** A small, complete OpenAPI 3.1 document for the tests (fictional SandPay API). */
function document(): OpenApiDocument {
  const problem = { $ref: '#/components/schemas/Problem' };
  return {
    openapi: '3.1.2',
    info: { title: 'SandPay test API', version: '1.0.0' },
    paths: {
      '/orders': {
        get: {
          operationId: 'listOrders',
          responses: {
            '200': {
              description: 'Orders',
              content: {
                'application/json': {
                  schema: { type: 'array', items: { $ref: '#/components/schemas/Order' } },
                },
              },
            },
            '4XX': {
              description: 'Client error',
              content: { 'application/problem+json': { schema: problem } },
            },
          },
        },
      },
      '/orders/{orderId}': {
        get: {
          operationId: 'getOrder',
          responses: {
            '200': {
              description: 'The order',
              content: { 'application/json': { schema: { $ref: '#/components/schemas/Order' } } },
            },
            '404': { $ref: '#/components/responses/NotFound' },
            default: {
              description: 'Unexpected error',
              content: { 'application/problem+json': { schema: problem } },
            },
          },
        },
        delete: {
          operationId: 'cancelOrder',
          responses: { '204': { description: 'Cancelled - no body' } },
        },
      },
      '/orders/summary': {
        get: {
          operationId: 'orderSummary',
          responses: {
            '200': {
              description: 'Totals',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    required: ['count'],
                    properties: { count: { type: 'integer' } },
                    additionalProperties: false,
                  },
                },
              },
            },
          },
        },
      },
    },
    components: {
      responses: {
        NotFound: {
          description: 'No such order',
          content: { 'application/problem+json': { schema: problem } },
        },
      },
      schemas: {
        Order: {
          type: 'object',
          required: ['id', 'amountMinor', 'createdAt'],
          additionalProperties: false,
          properties: {
            id: { type: 'string' },
            amountMinor: { type: 'integer', minimum: 0 },
            createdAt: { type: 'string', format: 'date-time' },
          },
        },
        Problem: {
          type: 'object',
          required: ['title', 'status'],
          properties: {
            type: { type: 'string', format: 'uri' },
            title: { type: 'string' },
            status: { type: 'integer' },
          },
        },
      },
    },
  };
}

const order = { id: 'ord_1001', amountMinor: 5000, createdAt: '2026-11-13T10:00:00.000Z' };
const notFound = {
  type: 'https://api.sandpay.example/problems/order-not-found',
  title: 'Order not found',
  status: 404,
};
const json = 'application/json; charset=utf-8';
const problemJson = 'application/problem+json; charset=utf-8';

describe('createContractChecker', { tags: ['@exercise'] }, () => {
  test('a response that matches the document has no problems', () => {
    const checker = createContractChecker(document());
    expect(
      checker.check({ method: 'GET', url: '/orders', status: 200, contentType: json, body: [order] }),
    ).toEqual([]);
    expect(
      checker.check({ method: 'GET', url: '/orders/ord_1001', status: 200, contentType: json, body: order }),
    ).toEqual([]);
  });

  test('ignores the query string and the content type parameters, and matches methods in any case', () => {
    const checker = createContractChecker(document());
    expect(
      checker.check({
        method: 'get',
        url: '/orders?status=paid&limit=5',
        status: 200,
        contentType: 'Application/JSON;charset=UTF-8',
        body: [],
      }),
    ).toEqual([]);
  });

  test('matches a concrete path before a templated one', () => {
    const checker = createContractChecker(document());
    // /orders/summary must use its own schema, not /orders/{orderId}'s Order schema.
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/summary',
        status: 200,
        contentType: json,
        body: { count: 3 },
      }),
    ).toEqual([]);
    expect(
      checker.check({ method: 'GET', url: '/orders/summary', status: 200, contentType: json, body: order })
        .length,
    ).toBeGreaterThan(0);
  });

  test('a template matches exactly one non-empty segment', () => {
    const checker = createContractChecker(document());
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/ord_1/refunds',
        status: 200,
        contentType: json,
        body: {},
      }),
    ).toEqual(['no documented path matches /orders/ord_1/refunds']);
    expect(
      checker.check({ method: 'GET', url: '/payments', status: 200, contentType: json, body: {} }),
    ).toEqual(['no documented path matches /payments']);
  });

  test('reports an undocumented method and an undocumented status', () => {
    const checker = createContractChecker(document());
    expect(
      checker.check({
        method: 'PATCH',
        url: '/orders/ord_1001',
        status: 200,
        contentType: json,
        body: order,
      }),
    ).toEqual(['PATCH is not documented for /orders/{orderId}']);
    expect(
      checker.check({ method: 'GET', url: '/orders', status: 500, contentType: problemJson, body: {} }),
    ).toEqual(['status 500 is not documented for GET /orders']);
  });

  test('uses the explicit code, then its range (4XX), then default', () => {
    const checker = createContractChecker(document());
    const problem400 = { title: 'Invalid query', status: 400 };
    expect(
      checker.check({
        method: 'GET',
        url: '/orders',
        status: 400,
        contentType: problemJson,
        body: problem400,
      }),
    ).toEqual([]);
    // 404 on /orders/{orderId} is explicit (via $ref); 503 falls to default.
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/ord_9',
        status: 404,
        contentType: problemJson,
        body: notFound,
      }),
    ).toEqual([]);
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/ord_9',
        status: 503,
        contentType: problemJson,
        body: { title: 'Down', status: 503 },
      }),
    ).toEqual([]);
  });

  test('follows a $ref to components/responses when validating', () => {
    const checker = createContractChecker(document());
    const problems = checker.check({
      method: 'GET',
      url: '/orders/ord_9',
      status: 404,
      contentType: problemJson,
      body: { title: 'Order not found' },
    });
    expect(problems).toEqual(["body: (body) must have required property 'status'"]);
  });

  test('reports a content type the response does not document', () => {
    const checker = createContractChecker(document());
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/ord_1001',
        status: 200,
        contentType: 'text/html',
        body: '<p>hi</p>',
      }),
    ).toEqual(['content type text/html is not documented for GET /orders/{orderId} 200']);
    expect(
      checker.check({
        method: 'GET',
        url: '/orders/ord_1001',
        status: 404,
        contentType: json,
        body: notFound,
      }),
    ).toEqual(['content type application/json is not documented for GET /orders/{orderId} 404']);
  });

  test('a response documented without content must have no body', () => {
    const checker = createContractChecker(document());
    expect(checker.check({ method: 'DELETE', url: '/orders/ord_1001', status: 204 })).toEqual([]);
    expect(
      checker.check({ method: 'DELETE', url: '/orders/ord_1001', status: 204, contentType: json, body: {} }),
    ).toEqual(['DELETE /orders/{orderId} 204 documents no body, but got application/json']);
  });

  test('lists every schema error in the body, with formats enforced', () => {
    const checker = createContractChecker(document());
    const problems = checker.check({
      method: 'GET',
      url: '/orders/ord_1001',
      status: 200,
      contentType: json,
      body: { id: 'ord_1001', amountMinor: 12.5, createdAt: 'yesterday', riskScore: 3 },
    });
    expect(problems).toEqual(
      expect.arrayContaining([
        'body: (body) must NOT have additional properties',
        'body: /amountMinor must be integer',
        'body: /createdAt must match format "date-time"',
      ]),
    );
    expect(problems).toHaveLength(3);
  });

  test('uncovered() lists documented responses no test has produced yet, in document order', () => {
    const checker = createContractChecker(document());
    expect(checker.uncovered()).toEqual([
      'GET /orders 200',
      'GET /orders 4XX',
      'GET /orders/{orderId} 200',
      'GET /orders/{orderId} 404',
      'GET /orders/{orderId} default',
      'DELETE /orders/{orderId} 204',
      'GET /orders/summary 200',
    ]);
    checker.check({ method: 'GET', url: '/orders', status: 200, contentType: json, body: [] });
    checker.check({
      method: 'GET',
      url: '/orders',
      status: 422,
      contentType: problemJson,
      body: { title: 'x', status: 422 },
    });
    checker.check({
      method: 'GET',
      url: '/orders/ord_9',
      status: 404,
      contentType: problemJson,
      body: notFound,
    });
    // A response that fails validation still counts as seen: the status was produced.
    checker.check({ method: 'GET', url: '/orders/summary', status: 200, contentType: json, body: {} });
    // An undocumented status covers nothing (GET /orders has no default; GET /orders/{orderId} has one).
    checker.check({ method: 'GET', url: '/orders', status: 503, contentType: json, body: {} });
    expect(checker.uncovered()).toEqual([
      'GET /orders/{orderId} 200',
      'GET /orders/{orderId} default',
      'DELETE /orders/{orderId} 204',
    ]);
  });
});
