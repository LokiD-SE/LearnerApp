// Shared by both openapi exercises - you don't need to change this file.
// Ajv set up for OpenAPI 3.1 Schema Objects: JSON Schema draft 2020-12, enforced formats, and the
// OpenAPI-specific keywords allowed so Ajv's strict mode accepts a whole OpenAPI document.
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormatsModule from 'ajv-formats';

// ajv-formats is a CommonJS module; under NodeNext its default export arrives wrapped.
const addFormats = addFormatsModule as unknown as (ajv: Ajv2020) => Ajv2020;

/** A parsed OpenAPI document. Only the parts the exercises read are typed. */
export interface OpenApiDocument {
  openapi: string;
  info: { title: string; version: string };
  paths?: Record<string, Record<string, unknown>>;
  components?: { schemas?: Record<string, unknown> } & Record<string, unknown>;
  [field: string]: unknown;
}

/**
 * Keywords Ajv's strict mode would reject as unknown: the top-level fields of an OpenAPI document,
 * and the OAS base vocabulary (discriminator, xml, externalDocs, example) - OpenAPI 3.1 section 4.8.24.2.
 */
const OPENAPI_KEYWORDS = [
  'openapi',
  'info',
  'jsonSchemaDialect',
  'servers',
  'paths',
  'webhooks',
  'components',
  'security',
  'tags',
  'externalDocs',
  'discriminator',
  'xml',
  'example',
];

export const DOCUMENT_ID = 'https://api.sandpay.example/openapi.yaml';

/**
 * Returns an Ajv instance that knows the whole document under DOCUMENT_ID, so a schema anywhere in
 * it - and every $ref such as '#/components/schemas/Order' inside it - can be compiled.
 */
export function createOasAjv(doc: OpenApiDocument): Ajv2020 {
  const ajv = new Ajv2020({ allErrors: true });
  addFormats(ajv);
  ajv.addVocabulary(OPENAPI_KEYWORDS);
  ajv.addSchema(doc, DOCUMENT_ID);
  return ajv;
}

/** Escapes one key for a JSON Pointer (RFC 6901) and a URI fragment: '/orders/{id}' -> '~1orders~1%7Bid%7D'. */
export function pointerSegment(key: string): string {
  return encodeURIComponent(key.replace(/~/g, '~0').replace(/\//g, '~1'));
}

/** Validator for the schema at a JSON Pointer path inside the document, for example
 * ['paths', '/orders/{orderId}', 'get', 'responses', '200', 'content', 'application/json', 'schema']. */
export function validatorAt(ajv: Ajv2020, path: string[]) {
  const ref = `${DOCUMENT_ID}#/${path.map(pointerSegment).join('/')}`;
  const validate = ajv.getSchema(ref);
  if (!validate) throw new Error(`No schema at ${ref}`);
  return validate;
}

/** Ajv's errors as short readable lines: '/amountMinor must be integer'. */
export function describeErrors(
  errors: readonly { instancePath: string; message?: string }[] | null | undefined,
): string[] {
  return (errors ?? []).map((e) => `${e.instancePath || '(body)'} ${e.message ?? 'is invalid'}`);
}
