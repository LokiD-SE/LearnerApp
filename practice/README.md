# Practice projects

Code you write and run on your own computer. Each coding exercise in LearnerApp names a project, the
files to change, the test class that checks them and the command to run.

| Folder          | Track    | What you practise                           | Needs               |
| --------------- | -------- | ------------------------------------------- | ------------------- |
| [`java/`](java) | E - Java | Small Java exercises checked by JUnit tests | JDK 17+, Maven 3.8+ |

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

## Troubleshooting

| Symptom                                           | Cause and fix                                                                                                                                                                                          |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `release version 17 not supported`                | Maven is running on a Java **runtime** without a compiler, or on a JDK without the files `--release` needs. Install a full JDK 17+ and point `JAVA_HOME` at it (`mvn -v` shows which Java Maven uses). |
| `The practice projects need Java 17 or later`     | Maven runs on an older Java. Set `JAVA_HOME` to a JDK 17+.                                                                                                                                             |
| `No tests matching pattern "XTest" were executed` | Check the class name in `-Dtest=` - it is the test class, without `.java`.                                                                                                                             |
| The first run is slow                             | Maven downloads its plugins and JUnit once into `~/.m2/repository`.                                                                                                                                    |

## For maintainers: changing an exercise

`practice/verify.sh <project>` is what CI runs. It checks that the reference solutions pass every test,
that every exercise test class **fails** against the unsolved exercise (so the tests really check the
work), and that tests which are not exercises pass either way. Lessons link to these files, and a
LearnerApp content test fails if a linked file is missing.
