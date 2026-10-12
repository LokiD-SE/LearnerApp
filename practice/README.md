# Practice projects

Code you write and run on your own computer. Each coding exercise in LearnerApp names a project, the
files to change, the test class that checks them and the command to run.

| Folder                      | Track                          | What you practise                                                                                                                            | Needs                                               |
| --------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [`java/`](java)             | E - Java                       | Small Java exercises checked by JUnit tests                                                                                                  | JDK 17+, Maven 3.8+                                 |
| [`framework/`](framework)   | F, G - Selenium and frameworks | A small reference framework, and exercises for locators, waits and page objects                                                              | JDK 17+, Maven 3.8+, Google Chrome                  |
| [`maven/`](maven)           | G - Maven                      | Broken `pom.xml` files to fix; tests run Maven on them and check the result                                                                  | JDK 17+, Maven 3.8+                                 |
| [`playwright/`](playwright) | H - Playwright                 | Playwright Test in TypeScript (and one JavaScript exercise): async code, locators, waits, page objects, fixtures, network mocking, API tests | Node.js 20+; Playwright's Chromium or Google Chrome |
| [`shop/`](shop)             | -                              | The SandPay Demo Shop the framework tests: static HTML, CSS and JavaScript                                                                   | a browser                                           |

## How every project works

- `src/exercises/java` - **your code**. Each class says which lesson it belongs to, which test checks
  it and how to run that test.
- `src/test/java` - the tests. Exercise test classes are tagged `@Tag("exercise")`. Don't edit them to
  make them pass.
- `src/solutions/java` - reference solutions, the same classes solved. Look after you have tried.
  `mvn -Psolutions test` builds and tests against them instead of your code.

```bash
cd practice/java
mvn test -Dtest=MoneyTest        # one exercise
mvn test                          # every exercise (the unsolved ones fail)
mvn -Psolutions test              # every test against the reference solutions
```

## The SandPay Demo Shop

A fictional shop built to be awkward in the ways real web apps are: products load asynchronously,
sorting re-renders the list, ids and one CSS class are generated on every load, card details are in an
iframe, an overlay covers the page while a payment runs, and some payments stay PENDING until the order
page updates. Stable `data-testid` attributes are the intended test hooks. Test cards are codes, not
card numbers:

| Code                          | Outcome                                 |
| ----------------------------- | --------------------------------------- |
| `sandpay-success`             | paid after about 1.5 s                  |
| `sandpay-slow`                | paid after about 4 s                    |
| `sandpay-insufficient-funds`  | declined: insufficient funds            |
| `sandpay-card-declined`       | declined by the card issuer             |
| `sandpay-unknown`             | PENDING, then SUCCEEDED about 3 s later |
| `sandpay-pending-then-failed` | PENDING, then FAILED about 3 s later    |

It is published with LearnerApp at `shop/` (for example `https://lokid-se.github.io/LearnerApp/shop/`),
and `npm run dev` serves it at `http://localhost:5173/shop/`.

## The reference framework

```bash
cd practice/framework
mvn test -Dtest=CheckoutJourneyTest                    # watch it in a Chrome window
mvn test -Dheadless=true                               # no window (the default in CI)
mvn test -Dshop.url=https://lokid-se.github.io/LearnerApp/shop/   # against the published shop
```

| Setting             | Default                                                    | Meaning                             |
| ------------------- | ---------------------------------------------------------- | ----------------------------------- |
| `-Dheadless`        | `true` when the `CI` variable is `true`, otherwise `false` | run Chrome without a window         |
| `-Dshop.url`        | empty: serve `-Dshop.dir` locally                          | test a shop that is already running |
| `-Dshop.dir`        | `../shop`                                                  | the shop's files                    |
| `-Dtimeout.seconds` | `10`                                                       | the longest any wait waits          |

Failed tests leave a screenshot and the page source in `target/evidence`.

## The Playwright project

`practice/playwright` is a Node project. Exercises are in `exercises/`, their tests in `tests/` (tagged
`@exercise`), reference solutions in `solutions/`, and given page objects in `framework/pages`.

```bash
cd practice/playwright
npm ci
npx playwright install chromium               # once - or use Google Chrome: PW_CHANNEL=chrome
npx playwright test tests/shop-locators.spec.ts
npx playwright test --ui                      # watch, step through, pick locators
npm run typecheck                             # Playwright runs TypeScript but doesn't type-check it
npm run test:solutions                        # every test against the reference solutions
```

`npm run verify` (what CI runs through `practice/verify.sh playwright`) type-checks, runs the solutions,
checks that every exercise spec fails against the unsolved exercises, and runs the journey tests. Set
`SHOP_URL=https://lokid-se.github.io/LearnerApp/shop/` to test the published shop instead of the local one.

## The Maven exercises

Each exercise is a small Maven project of its own in `practice/maven/src/exercises/projects/<name>`. Fix its
`pom.xml` - build it there with `mvn test` while you work - then run the exercise's test class from
`practice/maven`. The test class runs Maven on your project (the same Maven you started it with) and checks
what happened: whether it builds, how many tests really ran, which phase ran the integration tests, and
whether a failing test fails the build.

```bash
cd practice/maven/src/exercises/projects/receipt-tool && mvn test   # work on the exercise
cd practice/maven && mvn test -Dtest=ReceiptToolBuildTest           # check it
```

## Troubleshooting

| Symptom                                             | Cause and fix                                                                                                                                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `release version 17 not supported`                  | Maven is running on a Java **runtime** without a compiler, or on a JDK without the files `--release` needs. Install a full JDK 17+ and point `JAVA_HOME` at it (`mvn -v` shows which Java Maven uses). |
| `The practice projects need Java 17 or later`       | Maven runs on an older Java. Set `JAVA_HOME` to a JDK 17+.                                                                                                                                             |
| `No tests matching pattern "XTest" were executed`   | Check the class name in `-Dtest=` - it is the test class, without `.java`.                                                                                                                             |
| The first run is slow                               | Maven downloads its plugins and JUnit once into `~/.m2/repository`.                                                                                                                                    |
| `SessionNotCreatedException`                        | Chrome is missing or could not start. Install Google Chrome; on a server without a display add `-Dheadless=true`.                                                                                      |
| `Unable to find an exact match for CDP version ...` | A harmless warning: your Chrome is newer than this Selenium version knows. The framework doesn't use CDP; a newer Selenium silences it.                                                                |

## For maintainers: changing an exercise

`practice/verify.sh <project>` is what CI runs. It checks that the reference solutions pass every test,
that every exercise test class **fails** against the unsolved exercise (so the tests really check the
work), and that tests which are not exercises pass either way. Lessons link to these files, and a
LearnerApp content test fails if a linked file is missing.
