#!/usr/bin/env bash
# Verifies a practice project, for CI and for anyone changing an exercise:
#   1. every test passes against the reference solutions (src/solutions/java);
#   2. every exercise test class (@Tag("exercise")) fails against the unsolved exercises
#      (src/exercises/java) - otherwise its tests do not check the learner's work;
#   3. every other test passes against the unsolved exercises too.
# Usage: practice/verify.sh <project folder name> [extra Maven arguments]
set -euo pipefail

project="${1:?usage: practice/verify.sh <project> [maven args]}"
shift
cd "$(dirname "$0")/$project"

# Node projects (practice/playwright) verify themselves the same way: scripts/verify.mjs
if [ -f package.json ]; then
  [ -d node_modules ] || npm ci --no-audit --no-fund
  exec npm run verify -- "$@"
fi

mvn=(mvn -B -ntp "$@")

echo "== $project: reference solutions must pass every test"
"${mvn[@]}" -Psolutions clean verify

echo "== $project: unsolved exercises must fail every exercise test class"
reports=target/surefire-reports
"${mvn[@]}" clean test -Dgroups=exercise -Dmaven.test.failure.ignore=true
shopt -s nullglob
files=("$reports"/TEST-*.xml)
if [ ${#files[@]} -eq 0 ]; then
  echo "no exercise test classes found in $project" >&2
  exit 1
fi
status=0
for report in "${files[@]}"; do
  suite=$(grep -m1 -o '<testsuite [^>]*>' "$report")
  name=$(sed -E 's/.* name="([^"]*)".*/\1/' <<<"$suite")
  failures=$(sed -E 's/.* failures="([0-9]+)".*/\1/' <<<"$suite")
  errors=$(sed -E 's/.* errors="([0-9]+)".*/\1/' <<<"$suite")
  if [ $((failures + errors)) -eq 0 ]; then
    echo "FAIL: $name passes against the unsolved exercise, so it does not check the work" >&2
    status=1
  else
    echo "ok: $name fails against the unsolved exercise ($failures failures, $errors errors)"
  fi
done

echo "== $project: tests that are not exercises must pass against the unsolved exercises"
"${mvn[@]}" clean test -DexcludedGroups=exercise -Dsurefire.failIfNoSpecifiedTests=false

exit $status
