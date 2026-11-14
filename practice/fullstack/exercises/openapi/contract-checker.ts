// Exercise 2: a contract checker for the API's own test suite. Every response a test sees is checked
// against the OpenAPI document, and the checker remembers which documented responses were never
// produced - a coverage report for the contract. See the lesson for the rules; the tests in
// tests/openapi/contract-checker.test.ts spell them out.
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

// Helpers you will probably want - already imported for you.
void createOasAjv;
void describeErrors;
void validatorAt;

export function createContractChecker(doc: OpenApiDocument): ContractChecker {
  void doc;
  // TODO 1: find the documented path for observed.url - concrete paths before templated ones,
  //         one {template} matches exactly one non-empty segment, ignore the query string.
  // TODO 2: find the operation for the method, then the response: explicit status, then its range
  //         (4XX), then default. Mark that response as covered.
  // TODO 3: check the content type (without '; charset=...') is documented, and validate the body
  //         against its schema - following a $ref to components/responses if there is one.
  // TODO 4: uncovered() lists every documented response never matched, as 'GET /orders 200'.
  return {
    check() {
      throw new Error('TODO: check a response against the document');
    },
    uncovered() {
      throw new Error('TODO: list the documented responses never seen');
    },
  };
}
