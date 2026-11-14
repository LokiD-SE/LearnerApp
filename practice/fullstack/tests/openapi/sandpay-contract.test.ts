import { readFileSync } from 'node:fs';
import request from 'supertest';
import { parse } from 'yaml';
import {
  createOasAjv,
  describeErrors,
  validatorAt,
  type OpenApiDocument,
} from '../../exercises/openapi/oas-ajv.js';
import { createOrdersApp } from '../../exercises/openapi/orders-app.js';

const file = new URL('../../exercises/openapi/sandpay-openapi.yaml', import.meta.url);

function loadDocument(): OpenApiDocument {
  return parse(readFileSync(file, 'utf8')) as OpenApiDocument;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- walks an untyped OpenAPI document
type Json = Record<string, any>;

/** The Operation Object for a method on a path, or a clear failure. */
function operation(doc: OpenApiDocument, path: string, method: string): Json {
  const item = doc.paths?.[path] as Json | undefined;
  expect(item, `paths['${path}'] is missing`).toBeDefined();
  const op = item?.[method] as Json | undefined;
  expect(op, `${method.toUpperCase()} ${path} is not described`).toBeDefined();
  return op as Json;
}

/** Follows a local $ref such as '#/components/responses/NotFound'. */
function deref(doc: OpenApiDocument, value: Json): Json {
  if (typeof value?.$ref !== 'string') return value;
  const target = value.$ref
    .replace(/^#\//, '')
    .split('/')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- walks an untyped OpenAPI document
    .reduce((node: any, key: string) => node?.[key.replace(/~1/g, '/').replace(/~0/g, '~')], doc);
  expect(target, `${value.$ref} does not resolve`).toBeDefined();
  return deref(doc, target);
}

/** The documented Response Object for an explicit status code (exercise 2 handles ranges and default). */
function documentedResponse(doc: OpenApiDocument, path: string, method: string, status: number): Json {
  const op = operation(doc, path, method);
  const response = op.responses?.[String(status)];
  expect(response, `${method.toUpperCase()} ${path} does not document a ${status} response`).toBeDefined();
  return deref(doc, response);
}

/**
 * Checks one real response against the document: the status is documented, the content type is one
 * the response documents, and the body matches that schema.
 */
function expectConforms(doc: OpenApiDocument, path: string, method: string, res: request.Response): void {
  const documented = documentedResponse(doc, path, method, res.status);
  const contentType = String(res.headers['content-type'] ?? '')
    .split(';')[0]!
    .trim();
  const media = documented.content?.[contentType];
  expect(
    media,
    `${res.status} from ${method.toUpperCase()} ${path} is ${contentType}, which is not documented`,
  ).toBeDefined();
  const ajv = createOasAjv(doc);
  // Point at the response where it is defined, so $refs to components/responses work too.
  const responseRef = (operation(doc, path, method).responses[String(res.status)] as Json).$ref as
    string | undefined;
  const base = responseRef
    ? responseRef
        .replace(/^#\//, '')
        .split('/')
        .map((k) => k.replace(/~1/g, '/').replace(/~0/g, '~'))
    : ['paths', path, method, 'responses', String(res.status)];
  const validate = validatorAt(ajv, [...base, 'content', contentType, 'schema']);
  const ok = validate(res.body);
  expect(
    describeErrors(validate.errors),
    `body of ${res.status} from ${method.toUpperCase()} ${path}`,
  ).toEqual([]);
  expect(ok).toBe(true);
}

describe('the SandPay OpenAPI document', { tags: ['@exercise'] }, () => {
  describe('the document itself', () => {
    test('is OpenAPI 3.1 with a title and a version', () => {
      const doc = loadDocument();
      expect(doc.openapi).toMatch(/^3\.1\.\d+$/);
      expect(doc.info?.title).toBeTruthy();
      expect(doc.info?.version).toBeTruthy();
    });

    test('names every operation with a unique operationId', () => {
      const doc = loadDocument();
      expect(operation(doc, '/orders', 'get').operationId).toBe('listOrders');
      expect(operation(doc, '/orders/{orderId}', 'get').operationId).toBe('getOrder');
      expect(operation(doc, '/orders/{orderId}/refunds', 'post').operationId).toBe('createRefund');
      const ids = Object.values(doc.paths ?? {}).flatMap((item) =>
        Object.entries(item)
          .filter(([key]) =>
            ['get', 'put', 'post', 'delete', 'patch', 'options', 'head', 'trace'].includes(key),
          )
          .map(([, op]) => (op as Json).operationId as string | undefined),
      );
      expect(ids.every(Boolean), 'an operation has no operationId').toBe(true);
      expect(new Set(ids).size, `operationIds must be unique: ${ids.join(', ')}`).toBe(ids.length);
    });

    test('declares every path template as a required path parameter', () => {
      const doc = loadDocument();
      for (const [path, item] of Object.entries(doc.paths ?? {})) {
        const names = [...path.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]);
        for (const [method, op] of Object.entries(item)) {
          if (method === 'parameters' || typeof op !== 'object' || op === null) continue;
          const params = [
            ...(((item as Json).parameters as Json[]) ?? []),
            ...(((op as Json).parameters as Json[]) ?? []),
          ].map((p) => deref(doc, p));
          for (const name of names) {
            const param = params.find((p) => p.in === 'path' && p.name === name);
            expect(
              param,
              `${method.toUpperCase()} ${path} does not declare path parameter ${name}`,
            ).toBeDefined();
            expect(param?.required, `path parameter ${name} must have required: true`).toBe(true);
          }
        }
      }
    });

    test('gives every response a description', () => {
      const doc = loadDocument();
      for (const [path, item] of Object.entries(doc.paths ?? {})) {
        for (const [method, op] of Object.entries(item)) {
          if (method === 'parameters') continue;
          for (const [status, response] of Object.entries(((op as Json).responses ?? {}) as Json)) {
            expect(
              deref(doc, response as Json).description,
              `${method.toUpperCase()} ${path} ${status} has no description`,
            ).toBeTruthy();
          }
        }
      }
    });

    test('uses JSON Schema 2020-12, not OpenAPI 3.0 keywords', () => {
      const text = readFileSync(file, 'utf8');
      expect(text, 'nullable is OpenAPI 3.0 - in 3.1 write type: [string, "null"]').not.toMatch(
        /^\s*nullable:/m,
      );
      expect(text, 'exclusiveMinimum/Maximum are numbers in 3.1, not booleans').not.toMatch(
        /exclusive(Minimum|Maximum):\s*(true|false)/,
      );
      // Every schema in the document compiles in Ajv's strict mode (formats enforced).
      expect(() =>
        createOasAjv(loadDocument()).compile({ $ref: 'https://api.sandpay.example/openapi.yaml' }),
      ).not.toThrow();
    });
    test('describes an order tightly enough to catch a broken response', () => {
      const doc = loadDocument();
      const validate = validatorAt(createOasAjv(doc), ['components', 'schemas', 'Order']);
      const good = {
        id: 'ord_1001',
        amountMinor: 5000,
        currency: 'EUR',
        status: 'paid',
        customerNote: null,
        createdAt: '2026-11-13T10:00:00.000Z',
      };
      const goodIsValid = validate(good);
      expect(describeErrors(validate.errors), 'a real order must be valid').toEqual([]);
      expect(goodIsValid).toBe(true);
      const broken: [string, object][] = [
        ['a fractional amount', { ...good, amountMinor: 50.5 }],
        ['an amount sent as a string', { ...good, amountMinor: '5000' }],
        ['a missing currency', (({ currency: _c, ...rest }) => rest)(good)],
        [
          'a missing customerNote (null is fine, absent is not)',
          (({ customerNote: _n, ...rest }) => rest)(good),
        ],
        ['an unknown status', { ...good, status: 'lost' }],
        ['a negative amount', { ...good, amountMinor: -1 }],
        ['a date that is not RFC 3339', { ...good, createdAt: '13/11/2026' }],
        ['a property the API never sends', { ...good, internalRiskScore: 12 }],
      ];
      for (const [what, order] of broken) {
        expect(validate(order), `the Order schema accepts ${what}`).toBe(false);
      }
      expect(validate({ ...good, status: 'failed' }), "'failed' is a status the app uses").toBe(true);
    });
  });

  describe('the running app conforms to it', () => {
    test('GET /orders: a page of orders', async () => {
      const res = await request(createOrdersApp()).get('/orders?status=paid&limit=5');
      expect(res.status).toBe(200);
      expectConforms(loadDocument(), '/orders', 'get', res);
    });

    test('GET /orders with a bad limit: 400 Problem Details', async () => {
      const res = await request(createOrdersApp()).get('/orders?limit=0');
      expect(res.status).toBe(400);
      expectConforms(loadDocument(), '/orders', 'get', res);
    });

    test('GET /orders/{orderId}: an order with a note and one without', async () => {
      const app = createOrdersApp();
      const doc = loadDocument();
      for (const id of ['ord_1001', 'ord_1002']) {
        const res = await request(app).get(`/orders/${id}`);
        expect(res.status).toBe(200);
        expectConforms(doc, '/orders/{orderId}', 'get', res);
      }
    });

    test('GET /orders/{orderId} for an unknown order: 404 Problem Details', async () => {
      const res = await request(createOrdersApp()).get('/orders/ord_9999');
      expect(res.status).toBe(404);
      expectConforms(loadDocument(), '/orders/{orderId}', 'get', res);
    });

    test('POST /orders/{orderId}/refunds: 201 with a Location header the document promises', async () => {
      const doc = loadDocument();
      const res = await request(createOrdersApp())
        .post('/orders/ord_1001/refunds')
        .send({ amountMinor: 1200, reason: 'Item returned' });
      expect(res.status).toBe(201);
      expectConforms(doc, '/orders/{orderId}/refunds', 'post', res);
      const headers = documentedResponse(doc, '/orders/{orderId}/refunds', 'post', 201).headers ?? {};
      expect(Object.keys(headers), 'the 201 response must document its Location header').toContain(
        'Location',
      );
      expect(res.headers.location).toBe('/orders/ord_1001/refunds/re_0001');
    });

    test('POST refunds: 400, 404 and 409 are documented Problem Details', async () => {
      const app = createOrdersApp();
      const doc = loadDocument();
      const cases: [string, object, number][] = [
        ['/orders/ord_1001/refunds', { amountMinor: 0, reason: 'x' }, 400],
        ['/orders/ord_9999/refunds', { amountMinor: 100, reason: 'x' }, 404],
        ['/orders/ord_1002/refunds', { amountMinor: 999999, reason: 'Too much' }, 409],
        ['/orders/ord_1003/refunds', { amountMinor: 100, reason: 'Not paid yet' }, 409],
      ];
      for (const [url, body, status] of cases) {
        const res = await request(app).post(url).send(body);
        expect(res.status, `${url} ${JSON.stringify(body)}`).toBe(status);
        expectConforms(doc, '/orders/{orderId}/refunds', 'post', res);
      }
    });

    test('the request body schema accepts what the app accepts and rejects what it rejects', async () => {
      const doc = loadDocument();
      const op = operation(doc, '/orders/{orderId}/refunds', 'post');
      expect(op.requestBody?.required, 'the refund body is required').toBe(true);
      expect(op.requestBody?.content?.['application/json'], 'document the JSON request body').toBeDefined();
      const validate = validatorAt(createOasAjv(doc), [
        'paths',
        '/orders/{orderId}/refunds',
        'post',
        'requestBody',
        'content',
        'application/json',
        'schema',
      ]);
      const app = createOrdersApp();
      const bodies: object[] = [
        { amountMinor: 100, reason: 'Item returned' },
        { amountMinor: 0, reason: 'Zero' },
        { amountMinor: 1.5, reason: 'Fraction' },
        { amountMinor: 100 },
        { amountMinor: 100, reason: '' },
        { amountMinor: 100, reason: 'x'.repeat(201) },
        { amountMinor: 100, reason: 'Extra field', refundAll: true },
      ];
      for (const body of bodies) {
        const res = await request(app).post('/orders/ord_1001/refunds').send(body);
        const appAccepts = res.status === 201;
        expect(validate(body), `schema and app disagree on ${JSON.stringify(body)}`).toBe(appAccepts);
      }
    });
  });
});
