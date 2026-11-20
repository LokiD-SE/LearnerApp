"""A local TLS server and certificate helpers for the testing-cryptography-and-data-exposure lesson.

Loopback only, like every practice target. Nothing here talks to the internet.

``serve_tls(variant)`` starts a tiny HTTPS server on 127.0.0.1 with a throw-away self-signed certificate and
yields ``(host, port, cert_path)``. The variants differ only in the TLS versions the server accepts:

| variant  | accepts          |
| -------- | ---------------- |
| modern   | TLS 1.2 and 1.3  |
| tls12    | TLS 1.2 only     |
| tls13    | TLS 1.3 only     |

The legacy versions (SSL 3.0, TLS 1.0, TLS 1.1) cannot be offered here: the OpenSSL that Python and the
``openssl`` command use on current systems refuses to speak them by default. The lesson explains why that is a
trap for testers (a client that cannot try a version reports "not supported", which is not the same as the
server refusing it).

``cert_facts(cert_path)`` reads a certificate with ``openssl x509 -text`` and returns the facts the exercise
checks: key size, signature algorithm, validity dates and the Subject Alternative Names.
"""

from __future__ import annotations

import atexit
import contextlib
import datetime as dt
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

VARIANTS = ("modern", "tls12", "tls13")
_VERSIONS = {
    "modern": (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3),
    "tls12": (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_2),
    "tls13": (ssl.TLSVersion.TLSv1_3, ssl.TLSVersion.TLSv1_3),
}


@lru_cache(maxsize=1)
def make_certificate() -> tuple[Path, Path]:
    """Creates (once per process) a 2048-bit RSA self-signed certificate for localhost; returns (cert, key)."""
    folder = Path(tempfile.mkdtemp(prefix="sandpay-tls-"))
    atexit.register(shutil.rmtree, folder, True)
    cert, key = folder / "cert.pem", folder / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "30",
         "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost/O=SandPay Practice",
         "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
        check=True, capture_output=True, timeout=30)
    return cert, key


def cert_facts(cert_path: str | Path) -> dict:
    """Facts about a certificate file, from ``openssl x509 -noout -text`` (no extra Python packages needed)."""
    text = subprocess.run(["openssl", "x509", "-in", str(cert_path), "-noout", "-text"],
                          check=True, capture_output=True, text=True, timeout=30).stdout

    def field(pattern: str) -> str:
        found = re.search(pattern, text)
        if not found:
            raise ValueError(f"certificate text has no {pattern!r}")
        return found.group(1).strip()

    def parse(value: str) -> dt.datetime:
        return dt.datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)

    san_line = field(r"X509v3 Subject Alternative Name:[^\n]*\n\s*([^\n]+)")
    san = [item.split(":", 1)[1] for item in (part.strip() for part in san_line.split(",")) if ":" in item]
    return {
        "key_bits": int(field(r"Public-Key: \((\d+) bit\)")),
        "signature_algorithm": field(r"Signature Algorithm: (\S+)"),
        "not_before": parse(field(r"Not Before: ([^\n]+)")),
        "not_after": parse(field(r"Not After : ([^\n]+)")),
        "san": san,
    }


def _handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            body = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # keep test output quiet
            pass

    return Handler


@contextlib.contextmanager
def serve_tls(variant: str = "modern") -> Iterator[tuple[str, int, Path]]:
    """Serves HTTPS on 127.0.0.1 with the TLS versions of ``variant``; yields ``(host, port, cert_path)``."""
    if variant not in _VARIANTS_OK:
        raise ValueError(f"unknown variant {variant!r}; known: {VARIANTS}")
    cert, key = make_certificate()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version, context.maximum_version = _VERSIONS[variant]
    context.load_cert_chain(cert, key)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler())
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", server.server_address[1], cert
    finally:
        server.shutdown()
        server.server_close()


_VARIANTS_OK = frozenset(VARIANTS)
