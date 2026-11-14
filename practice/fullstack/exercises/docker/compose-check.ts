// Exercise: a reviewer for compose.yaml files - catch the Compose mistakes from the lesson before
// anyone runs `docker compose up`. Runs in Node with the `yaml` package; no Docker needed.
// Tests: tests/docker/compose-check.test.ts

import { parse } from 'yaml';

export type RuleId =
  | 'no-services'
  | 'image-not-pinned'
  | 'unknown-dependency'
  | 'healthy-dependency'
  | 'missing-healthcheck'
  | 'literal-secret'
  | 'db-port-public'
  | 'db-data-not-persisted'
  | 'undeclared-volume';

export interface ComposeProblem {
  rule: RuleId;
  /** The service the problem is in; absent only for no-services. */
  service?: string;
  /** A sentence for a human. Its wording is up to you. */
  message: string;
}

/**
 * Parses a Compose file and returns every problem (an empty array for a good file). Rules, from the
 * Compose specification and the official postgres image documentation:
 *
 * - `no-services` - there is no `services` mapping (or it is empty). Report only this and stop.
 * - `image-not-pinned` - a service's `image` has no tag or the tag `latest` ("postgres",
 *   "postgres:latest", "registry.example:5000/api"). A tag ("postgres:18") or a digest
 *   ("postgres@sha256:...") is fine. The tag is what follows the last ":" AFTER the last "/".
 * - `unknown-dependency` - `depends_on` (short list or long mapping) names a service that isn't defined.
 * - `healthy-dependency` - a service depends on a DATABASE service (one whose image name is
 *   "postgres", with or without a tag, digest or registry path) without `condition: service_healthy`.
 *   Short syntax counts as service_started. Report it on the dependent service.
 * - `missing-healthcheck` - a service is depended on with `condition: service_healthy` but has no
 *   usable `healthcheck` (none, `disable: true`, no `test`, or a test of "NONE" / ["NONE"]). A
 *   healthcheck without `test` could inherit the image's HEALTHCHECK, but the file alone can't show
 *   that, so require it. Report it on the service that lacks the check, once, however many services
 *   depend on it.
 * - `literal-secret` - an `environment` variable whose name ends in PASSWORD, SECRET, TOKEN or API_KEY
 *   has a literal, non-empty value - one that doesn't use interpolation ("${...}"). Environment is
 *   either a mapping or a list of "NAME=value" strings. Names ending in _FILE are fine (they point
 *   to a secret file).
 * - `db-port-public` - a database service publishes container port 5432 on all interfaces. Short
 *   syntax: "5432:5432", "15432:5432", "5432", or the number 5432; it is fine only when it starts with
 *   "127.0.0.1:" or "[::1]:". Long syntax: `target: 5432` without `host_ip` 127.0.0.1 or ::1.
 * - `db-data-not-persisted` - a database service has no volume mounted at its data directory. For
 *   image tags whose major version is 18 or more that is /var/lib/postgresql; below 18 it is
 *   /var/lib/postgresql/data; with no tag or a tag that doesn't start with a number, accept either.
 *   Volumes are short ("source:target[:mode]") or long (`target:`) syntax.
 * - `undeclared-volume` - a service mounts a NAMED volume (short syntax whose source doesn't start
 *   with ".", "/" or "~"; or long syntax with `type: volume` and a source) that isn't declared under
 *   the top-level `volumes`. Report it once per volume name per service.
 */
export function checkCompose(yamlText: string): ComposeProblem[] {
  // TODO: check the rules above. This version only parses the file and approves everything.
  const doc: unknown = parse(yamlText);
  void doc;
  return [];
}
