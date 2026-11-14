import { checkCompose, type ComposeProblem } from '../../exercises/docker/compose-check.js';

/** "rule:service" pairs, sorted, so tests don't depend on order or message wording. */
const found = (problems: ComposeProblem[]) =>
  problems.map((p) => (p.service ? `${p.rule}:${p.service}` : p.rule)).sort();

const good = `
services:
  api:
    build: .
    image: sandpay/merchant-api:1.4.0
    ports:
      - "3000:3000"
    environment:
      DATABASE_HOST: db
      DATABASE_PASSWORD_FILE: /run/secrets/db_password
      SESSION_SECRET: \${SESSION_SECRET:?set SESSION_SECRET in .env}
    depends_on:
      db:
        condition: service_healthy
        restart: true
    secrets:
      - db_password
  db:
    image: postgres:18
    environment:
      POSTGRES_DB: sandpay
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d sandpay"]
      interval: 10s
      retries: 5
      start_period: 30s
    volumes:
      - db-data:/var/lib/postgresql
    ports:
      - "127.0.0.1:5432:5432"
    secrets:
      - db_password
volumes:
  db-data:
secrets:
  db_password:
    file: ./db_password.txt
`;

describe('checkCompose', { tags: ['@exercise'] }, () => {
  test('a good file has no problems', () => {
    expect(checkCompose(good)).toEqual([]);
  });

  test('every problem names a rule and a message', () => {
    const problems = checkCompose('services:\n  web:\n    image: nginx\n');
    expect(problems).toHaveLength(1);
    expect(problems[0]).toMatchObject({ rule: 'image-not-pinned', service: 'web' });
    expect(problems[0]?.message.length).toBeGreaterThan(0);
  });

  test.each(['', 'version: "3"\n', 'services: {}\n', 'services:\n'])('no services: %j', (text) => {
    expect(found(checkCompose(text))).toEqual(['no-services']);
  });

  test.each([
    ['postgres', true],
    ['postgres:latest', true],
    ['registry.example:5000/sandpay/api', true],
    ['registry.example:5000/sandpay/api:latest', true],
    ['postgres:18', false],
    ['postgres:18.1-alpine', false],
    ['registry.example:5000/sandpay/api:1.4.0', false],
    ['postgres@sha256:0ed5d5928d4737458944eb604cc8509e245c3e19d02ad83935398bc4b991aac7', false],
  ])('image %s unpinned: %s', (image, unpinned) => {
    const problems = checkCompose(`services:\n  web:\n    image: "${image}"\n`);
    expect(problems.some((p) => p.rule === 'image-not-pinned')).toBe(unpinned);
  });

  test('a service built from a Dockerfile without an image is fine', () => {
    expect(checkCompose('services:\n  api:\n    build: .\n')).toEqual([]);
  });

  test('depends_on a service that does not exist', () => {
    const text = `
services:
  api:
    build: .
    depends_on: [cache]
  worker:
    build: .
    depends_on:
      queue:
        condition: service_started
`;
    expect(found(checkCompose(text))).toEqual(['unknown-dependency:api', 'unknown-dependency:worker']);
  });

  test('a database dependency must wait for service_healthy (short syntax only waits for "started")', () => {
    const db = `
  db:
    image: postgres:18
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
    volumes:
      - ./pgdata:/var/lib/postgresql
`;
    const short = `services:\n  api:\n    build: .\n    depends_on: [db]\n${db}`;
    expect(found(checkCompose(short))).toEqual(['healthy-dependency:api']);
    const started = `services:\n  api:\n    build: .\n    depends_on:\n      db:\n        condition: service_started\n${db}`;
    expect(found(checkCompose(started))).toEqual(['healthy-dependency:api']);
    const healthy = started.replace('service_started', 'service_healthy');
    expect(checkCompose(healthy)).toEqual([]);
  });

  test('waiting for service_healthy needs a healthcheck on that service - reported once', () => {
    const text = `
services:
  api:
    build: .
    depends_on:
      cache:
        condition: service_healthy
  worker:
    build: .
    depends_on:
      cache:
        condition: service_healthy
  cache:
    image: redis:8
`;
    expect(found(checkCompose(text))).toEqual(['missing-healthcheck:cache']);
  });

  test.each([
    ['disable: true', '      disable: true'],
    ['test NONE list', '      test: ["NONE"]'],
    ['test NONE string', '      test: NONE'],
    ['no test', '      interval: 5s'],
  ])('a disabled or empty healthcheck does not count (%s)', (_, body) => {
    const text = `
services:
  api:
    build: .
    depends_on:
      cache:
        condition: service_healthy
  cache:
    image: redis:8
    healthcheck:
${body}
`;
    expect(found(checkCompose(text))).toEqual(['missing-healthcheck:cache']);
  });

  test('literal secrets in environment, as a mapping or a list', () => {
    const text = `
services:
  api:
    build: .
    environment:
      DATABASE_PASSWORD: s3cret
      SANDPAY_API_KEY: sk_test_fake
      LOG_LEVEL: info
      PASSWORD_HINT: none
  worker:
    build: .
    environment:
      - JWT_SECRET=abc123
      - SESSION_TOKEN=\${SESSION_TOKEN}
      - EMPTY_PASSWORD=
      - DB_PASSWORD_FILE=/run/secrets/db_password
`;
    const problems = checkCompose(text);
    expect(found(problems)).toEqual(['literal-secret:api', 'literal-secret:api', 'literal-secret:worker']);
  });

  test.each([
    ['"5432:5432"', true],
    ['"15432:5432"', true],
    ['"5432"', true],
    ['5432', true],
    ['"0.0.0.0:5432:5432"', true],
    ['"127.0.0.1:5432:5432"', false],
    ['"[::1]:5432:5432"', false],
    ['"5433:5433"', false],
  ])('database port %s published publicly: %s', (port, publicPort) => {
    const text = good.replace('"127.0.0.1:5432:5432"', port);
    expect(checkCompose(text).some((p) => p.rule === 'db-port-public')).toBe(publicPort);
  });

  test('database port in long syntax', () => {
    const open = good.replace('- "127.0.0.1:5432:5432"', '- target: 5432\n        published: "5432"');
    expect(found(checkCompose(open))).toEqual(['db-port-public:db']);
    const local = good.replace(
      '- "127.0.0.1:5432:5432"',
      '- target: 5432\n        published: "5432"\n        host_ip: 127.0.0.1',
    );
    expect(checkCompose(local)).toEqual([]);
  });

  test('the same port on a service that is not a database is fine', () => {
    expect(checkCompose('services:\n  proxy:\n    image: haproxy:3.2\n    ports: ["5432:5432"]\n')).toEqual(
      [],
    );
  });

  test('database data must be on a volume at the right directory for the version', () => {
    const none = good.replace('    volumes:\n      - db-data:/var/lib/postgresql\n', '');
    expect(found(checkCompose(none))).toEqual(['db-data-not-persisted:db']);

    const oldPath = good.replace('db-data:/var/lib/postgresql', 'db-data:/var/lib/postgresql/data');
    expect(found(checkCompose(oldPath))).toEqual(['db-data-not-persisted:db']);

    const pg17 = oldPath.replace('postgres:18', 'postgres:17.6');
    expect(checkCompose(pg17)).toEqual([]);
    const pg17NewPath = good.replace('postgres:18', 'postgres:17');
    expect(found(checkCompose(pg17NewPath))).toEqual(['db-data-not-persisted:db']);

    const alpine19 = good.replace('postgres:18', 'postgres:19-alpine');
    expect(checkCompose(alpine19)).toEqual([]);
  });

  test('an untagged postgres image accepts either data directory', () => {
    const digest = 'postgres@sha256:0ed5d5928d4737458944eb604cc8509e245c3e19d02ad83935398bc4b991aac7';
    const text = good
      .replace('postgres:18', digest)
      .replace('db-data:/var/lib/postgresql', 'db-data:/var/lib/postgresql/data');
    expect(checkCompose(text)).toEqual([]);
  });

  test('a bind mount or long-syntax volume also persists the data', () => {
    const bind = good.replace('db-data:/var/lib/postgresql', './pgdata:/var/lib/postgresql');
    expect(checkCompose(bind)).toEqual([]);
    const long = good.replace(
      '- db-data:/var/lib/postgresql',
      '- type: volume\n        source: db-data\n        target: /var/lib/postgresql',
    );
    expect(checkCompose(long)).toEqual([]);
  });

  test('named volumes must be declared at the top level', () => {
    const undeclared = good.replace('volumes:\n  db-data:\n', '');
    expect(found(checkCompose(undeclared))).toEqual(['undeclared-volume:db']);

    const text = `
services:
  api:
    build: .
    volumes:
      - uploads:/srv/uploads
      - uploads:/srv/uploads-copy:ro
      - type: volume
        source: cache
        target: /srv/cache
      - ./src:/app/src
      - /var/log/api:/logs
      - ~/certs:/certs:ro
      - /anonymous
`;
    expect(found(checkCompose(text))).toEqual(['undeclared-volume:api', 'undeclared-volume:api']);
  });

  test('a file with several problems reports all of them', () => {
    const text = `
services:
  api:
    image: sandpay/merchant-api
    environment:
      DATABASE_PASSWORD: s3cret
    depends_on: [db]
  db:
    image: postgres:latest
    environment:
      POSTGRES_PASSWORD: s3cret
    ports:
      - "5432:5432"
`;
    expect(found(checkCompose(text))).toEqual([
      'db-data-not-persisted:db',
      'db-port-public:db',
      'healthy-dependency:api',
      'image-not-pinned:api',
      'image-not-pinned:db',
      'literal-secret:api',
      'literal-secret:db',
    ]);
  });
});
