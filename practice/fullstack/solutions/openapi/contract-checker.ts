// Exercise 2 (reference solution): a contract checker for the API's own test suite. Every response a
// test sees is checked against the OpenAPI document, and the checker remembers which documented
// responses were never produced - a coverage report for the contract.
import { createOasAjv, describeErrors, validatorAt, type OpenApiDocument } from './oas-ajv.js';

export interface ObservedResponse {
  method: string;
  /** Path and optional query, as the client requested it: '/orders/ord_1001?expand=refunds'. */
  url: string;
  status: number;
  /** The Content-Type header, parameters included ('application/json; charset=utf-8'), if any. */
  contentType?: string;
  body?: unknown;
}

export interface ContractChecker {
  /** What is wrong with the response; an empty array means it conforms to the document. */
  check(observed: ObservedResponse): string[];
  /** Documented responses no check has matched yet, in document order: 'GET /orders/{orderId} 404'. */
  uncovered(): string[];
}

const METHODS = ['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'];
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- walks an untyped OpenAPI document
type Json = Record<string, any>;

export function createContractChecker(doc: OpenApiDocument): ContractChecker {
  const ajv = createOasAjv(doc);
  const paths = Object.keys(doc.paths ?? {});

  // Every documented response, keyed 'GET /orders 200', in document order.
  const covered = new Map<string, boolean>();
  for (const path of paths) {
    const item = doc.paths![path] as Json;
    for (const method of METHODS) {
      for (const key of Object.keys(item[method]?.responses ?? {})) {
        covered.set(`${method.toUpperCase()} ${path} ${key}`, false);
      }
    }
  }

  /** OpenAPI 3.1 section 4.8.8: concrete paths match before templated ones; a template matches one segment. */
  function matchPath(url: string): string | undefined {
    const segments = url.split('?')[0]!.split('/');
    const matches = (template: string) => {
      const parts = template.split('/');
      return (
        parts.length === segments.length &&
        parts.every((part, i) => (/^\{[^}]+\}$/.test(part) ? segments[i] !== '' : part === segments[i]))
      );
    };
    return (
      paths.find((p) => !p.includes('{') && matches(p)) ?? paths.find((p) => p.includes('{') && matches(p))
    );
  }

  /** Section 4.8.16: an explicit code wins over its range (4XX), and default covers the rest. */
  function responseKey(responses: Json, status: number): string | undefined {
    return [String(status), `${String(status)[0]}XX`, 'default'].find((key) => key in responses);
  }

  /** JSON Pointer path to where a Response Object is really defined, following a local $ref. */
  function definedAt(pointer: string[], value: Json): { at: string[]; response: Json } {
    if (typeof value?.$ref !== 'string') return { at: pointer, response: value };
    const at = value.$ref
      .replace(/^#\//, '')
      .split('/')
      .map((k: string) => k.replace(/~1/g, '/').replace(/~0/g, '~'));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- walks an untyped OpenAPI document
    const target = at.reduce((node: any, key: string) => node?.[key], doc);
    return definedAt(at, target);
  }

  return {
    check(observed) {
      const method = observed.method.toLowerCase();
      const path = matchPath(observed.url);
      if (!path) return [`no documented path matches ${observed.url.split('?')[0]}`];
      const operation = (doc.paths![path] as Json)[method] as Json | undefined;
      if (!operation) return [`${method.toUpperCase()} is not documented for ${path}`];
      const label = `${method.toUpperCase()} ${path}`;
      const key = responseKey(operation.responses ?? {}, observed.status);
      if (!key) return [`status ${observed.status} is not documented for ${label}`];
      covered.set(`${label} ${key}`, true);

      const { at, response } = definedAt(['paths', path, method, 'responses', key], operation.responses[key]);
      const contentType = observed.contentType?.split(';')[0]!.trim().toLowerCase();
      const content = (response.content ?? {}) as Json;
      if (Object.keys(content).length === 0) {
        return contentType ? [`${label} ${observed.status} documents no body, but got ${contentType}`] : [];
      }
      if (!contentType || !(contentType in content)) {
        return [`content type ${contentType ?? '(none)'} is not documented for ${label} ${observed.status}`];
      }
      if (!content[contentType].schema) return [];
      const validate = validatorAt(ajv, [...at, 'content', contentType, 'schema']);
      return validate(observed.body) ? [] : describeErrors(validate.errors).map((e) => `body: ${e}`);
    },
    uncovered() {
      return [...covered].filter(([, seen]) => !seen).map(([key]) => key);
    },
  };
}
