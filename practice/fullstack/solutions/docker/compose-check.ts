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
  const doc = asRecord(parse(yamlText));
  const services = asRecord(doc?.services);
  if (!services || Object.keys(services).length === 0)
    return [{ rule: 'no-services', message: 'the file has no services' }];

  const problems: ComposeProblem[] = [];
  const add = (rule: RuleId, service: string, message: string) => problems.push({ rule, service, message });
  const declaredVolumes = new Set(Object.keys(asRecord(doc?.volumes) ?? {}));
  const needsHealthcheck = new Set<string>();

  for (const [name, raw] of Object.entries(services)) {
    const service = asRecord(raw) ?? {};
    const image = typeof service.image === 'string' ? service.image : undefined;

    if (image !== undefined && !isPinned(image))
      add('image-not-pinned', name, `image "${image}" has no version tag - pin a tag or a digest`);

    for (const [dependency, condition] of dependencies(service.depends_on)) {
      const target = asRecord(services[dependency]);
      if (!(dependency in services)) {
        add('unknown-dependency', name, `depends_on names "${dependency}", which isn't a service`);
        continue;
      }
      if (condition === 'service_healthy') needsHealthcheck.add(dependency);
      else if (isDatabase(target?.image))
        add('healthy-dependency', name, `wait for "${dependency}" with condition: service_healthy`);
    }

    for (const [variable, value] of environment(service.environment)) {
      if (/(PASSWORD|SECRET|TOKEN|API_KEY)$/.test(variable) && value !== '' && !value.includes('${'))
        add('literal-secret', name, `${variable} is written in the file - use a secret or \${${variable}:?}`);
    }

    const mounts = volumeMounts(service.volumes);
    const undeclared = new Set(
      mounts
        .filter((mount) => mount.named && !declaredVolumes.has(mount.source))
        .map((mount) => mount.source),
    );
    for (const volume of undeclared)
      add('undeclared-volume', name, `volume "${volume}" is not declared under the top-level volumes`);

    if (isDatabase(image)) {
      if (publishesPublicly(service.ports))
        add('db-port-public', name, 'port 5432 is published on every interface - bind it to 127.0.0.1');
      const targets = dataDirectories(image as string);
      if (!mounts.some((mount) => targets.includes(mount.target)))
        add('db-data-not-persisted', name, `mount a volume at ${targets.join(' or ')}`);
    }
  }

  for (const name of needsHealthcheck) {
    if (!hasHealthcheck(asRecord(services[name])))
      add('missing-healthcheck', name, 'services wait for this one to be healthy, but it has no healthcheck');
  }
  return problems;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function splitImage(image: string): { name: string; tag?: string; digest: boolean } {
  const at = image.indexOf('@');
  const withoutDigest = at === -1 ? image : image.slice(0, at);
  const digest = at === -1 ? undefined : image.slice(at + 1);
  const lastSlash = withoutDigest.lastIndexOf('/');
  const lastColon = withoutDigest.lastIndexOf(':');
  const hasTag = lastColon > lastSlash;
  const path = hasTag ? withoutDigest.slice(0, lastColon) : withoutDigest;
  return {
    name: path.slice(path.lastIndexOf('/') + 1),
    tag: hasTag ? withoutDigest.slice(lastColon + 1) : undefined,
    digest: digest !== undefined,
  };
}

function isPinned(image: string): boolean {
  const { tag, digest } = splitImage(image);
  return digest || (tag !== undefined && tag !== 'latest');
}

function isDatabase(image: unknown): boolean {
  return typeof image === 'string' && splitImage(image).name === 'postgres';
}

function dependencies(dependsOn: unknown): [string, string][] {
  if (Array.isArray(dependsOn)) return dependsOn.map((name) => [String(name), 'service_started']);
  const map = asRecord(dependsOn);
  if (!map) return [];
  return Object.entries(map).map(([name, options]) => [
    name,
    String(asRecord(options)?.condition ?? 'service_started'),
  ]);
}

function environment(env: unknown): [string, string][] {
  if (Array.isArray(env))
    return env.map((entry) => {
      const text = String(entry);
      const equals = text.indexOf('=');
      return equals === -1 ? [text, ''] : [text.slice(0, equals), text.slice(equals + 1)];
    });
  const map = asRecord(env);
  if (!map) return [];
  return Object.entries(map).map(([name, value]) => [
    name,
    value === null || value === undefined ? '' : String(value),
  ]);
}

interface Mount {
  source: string;
  target: string;
  named: boolean;
}

function volumeMounts(volumes: unknown): Mount[] {
  if (!Array.isArray(volumes)) return [];
  return volumes.flatMap((entry): Mount[] => {
    if (typeof entry === 'string') {
      const [first = '', second] = entry.split(':');
      if (second === undefined) return [{ source: '', target: first, named: false }]; // anonymous
      return [{ source: first, target: second, named: !/^[./~]/.test(first) }];
    }
    const long = asRecord(entry);
    if (!long || typeof long.target !== 'string') return [];
    const source = typeof long.source === 'string' ? long.source : '';
    return [{ source, target: long.target, named: long.type === 'volume' && source !== '' }];
  });
}

function dataDirectories(image: string): string[] {
  const major = /^(\d+)/.exec(splitImage(image).tag ?? '');
  if (!major) return ['/var/lib/postgresql', '/var/lib/postgresql/data'];
  return Number(major[1]) >= 18 ? ['/var/lib/postgresql'] : ['/var/lib/postgresql/data'];
}

function publishesPublicly(ports: unknown): boolean {
  if (!Array.isArray(ports)) return false;
  return ports.some((entry) => {
    if (typeof entry === 'number') return entry === 5432;
    if (typeof entry === 'string') {
      const withoutProtocol = entry.replace(/\/(tcp|udp)$/, '');
      const container = withoutProtocol.slice(withoutProtocol.lastIndexOf(':') + 1);
      if (container !== '5432') return false;
      return !(entry.startsWith('127.0.0.1:') || entry.startsWith('[::1]:'));
    }
    const long = asRecord(entry);
    if (!long || Number(long.target) !== 5432) return false;
    return !(long.host_ip === '127.0.0.1' || long.host_ip === '::1');
  });
}

function hasHealthcheck(service: Record<string, unknown> | undefined): boolean {
  const check = asRecord(service?.healthcheck);
  if (!check || check.disable === true) return false;
  const test = check.test;
  if (test === undefined) return false;
  if (test === 'NONE' || (Array.isArray(test) && test[0] === 'NONE')) return false;
  return true;
}
