#!/usr/bin/env bash
# Downloads Apache JMeter into tools/ (gitignored) and checks it against the SHA-512 Apache publishes.
# JMeter needs Java 8+; the practice project is tested with JDK 17 and 21.
set -euo pipefail
VERSION="${JMETER_VERSION:-5.6.3}"
cd "$(dirname "$0")/../tools" 2>/dev/null || { mkdir -p "$(dirname "$0")/../tools"; cd "$(dirname "$0")/../tools"; }
if [ -x "apache-jmeter-$VERSION/bin/jmeter" ]; then
  echo "JMeter $VERSION already in $(pwd)/apache-jmeter-$VERSION"
  exit 0
fi
archive="apache-jmeter-$VERSION.tgz"
curl -sSfL "https://dlcdn.apache.org/jmeter/binaries/$archive" -o "$archive" \
  || curl -sSfL "https://archive.apache.org/dist/jmeter/binaries/$archive" -o "$archive"
expected=$(curl -sSfL "https://downloads.apache.org/jmeter/binaries/$archive.sha512" \
  || curl -sSfL "https://archive.apache.org/dist/jmeter/binaries/$archive.sha512")
actual=$(sha512sum "$archive" | cut -d' ' -f1)
if ! grep -qi "$actual" <<<"$expected"; then
  echo "SHA-512 mismatch for $archive - not unpacking it" >&2
  rm -f "$archive"
  exit 1
fi
tar xzf "$archive"
rm -f "$archive"
echo "JMeter $VERSION in $(pwd)/apache-jmeter-$VERSION (SHA-512 verified)"
