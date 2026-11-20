"""Real JMeter distributed (remote) runs on one machine, loopback only - for the jmeter-distributed-testing lesson.

``remote_servers(count, workdir)`` starts ``count`` JMeter servers (``jmeter -s``, what ``bin/jmeter-server``
runs), each in its own working directory, so each one sees its own data files - as separate machines would.
``run_remote(plan, servers, gprops, out_dir)`` is the controller: ``jmeter -n -t plan -R host:port,... -G... -X``.

Loopback only, on purpose. JMeter 5.6.3's RMI code (``org.apache.jmeter.rmi.RmiUtils``) returns no server socket
factory when ``server.rmi.ssl.disable=true``, so Java's default factory listens on ALL interfaces - checked with
``ss -ltn`` on 20 November 2026. With SSL on, JMeter's ``SSLRMIServerSocketFactory`` binds to the RMI host, so this
fixture keeps SSL on, creates a throwaway keystore with ``keytool`` (what ``bin/create-rmi-keystore.sh`` runs) and
sets ``java.rmi.server.hostname=127.0.0.1`` on servers and controller. Every port is checked to be loopback-bound
before a test uses it.

The keystore is a practice key in a temporary folder: valid 7 days, password ``changeit`` (the manual's
defaults). Never reuse it for a real distributed setup.
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from load_tools import java_home, jmeter_home

HOST = "127.0.0.1"


@dataclass(frozen=True)
class RemoteServer:
    address: str  # "127.0.0.1:<registry port>", as -R wants it
    dir: Path  # the server's working directory - relative data file paths resolve here
    log: Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _env() -> dict[str, str]:
    env = {**os.environ, "HEAP": "-Xms128m -Xmx256m"}
    if java_home():
        env["JAVA_HOME"] = java_home()
    return env


def make_keystore(folder: Path) -> Path:
    """One key pair named ``rmi`` for every server and the controller, as section 13.1 of the manual describes."""
    keystore = folder / "rmi_keystore.jks"
    if keystore.exists():
        return keystore
    keytool = str(Path(java_home(), "bin", "keytool")) if java_home() else "keytool"
    subprocess.run([keytool, "-genkeypair", "-keyalg", "RSA", "-alias", "rmi", "-keystore", str(keystore),
                    "-storepass", "changeit", "-keypass", "changeit", "-validity", "7", "-keysize", "2048",
                    "-dname", "CN=rmi, OU=Practice, O=SandPay Practice, C=XY"],
                   check=True, capture_output=True, timeout=60)
    return keystore


def _ssl_props(keystore: Path) -> list[str]:
    return [f"-Jserver.rmi.ssl.keystore.file={keystore}", f"-Jserver.rmi.ssl.truststore.file={keystore}"]


def _listening_beyond_loopback(port: int) -> bool:
    """True if anything listens on ``port`` on a non-loopback address (Linux /proc/net/tcp*; False elsewhere)."""
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        with contextlib.suppress(OSError), open(table) as f:
            for line in list(f)[1:]:
                local, state = line.split()[1], line.split()[3]
                address, hex_port = local.split(":")
                if state != "0A" or int(hex_port, 16) != port:
                    continue
                loopback = {"0100007F", "00000000000000000000000001000000", "0000000000000000FFFF00000100007F"}
                if address not in loopback:
                    return True
    return False


@contextlib.contextmanager
def remote_servers(count: int, workdir: Path, timeout: float = 45) -> Iterator[list[RemoteServer]]:
    home = jmeter_home()
    if home is None:
        raise RuntimeError("JMeter not found - run scripts/get-jmeter.sh or set JMETER_HOME")
    workdir.mkdir(parents=True, exist_ok=True)
    keystore = make_keystore(workdir)
    servers, procs = [], []
    try:
        for n in range(1, count + 1):
            folder = workdir / f"server-{n}"
            folder.mkdir(exist_ok=True)
            port, local = _free_port(), _free_port()
            out = open(folder / "console.txt", "w")
            cmd = [str(home / "bin" / "jmeter"), f"-Djava.rmi.server.hostname={HOST}", f"-Dserver_port={port}",
                   "-s", "-j", "server.log", *_ssl_props(keystore), f"-Jserver.rmi.localport={local}",
                   ]  # the controller stops them with -X
            procs.append(subprocess.Popen(cmd, cwd=folder, stdout=out, stderr=subprocess.STDOUT, env=_env(),
                                          start_new_session=True))
            servers.append(RemoteServer(f"{HOST}:{port}", folder, folder / "server.log"))
        deadline = time.monotonic() + timeout
        for server, proc in zip(servers, procs):
            console = server.dir / "console.txt"
            while "Created remote object" not in console.read_text():
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"jmeter server {server.address} did not start:\n{console.read_text()}")
                time.sleep(0.1)
            if _listening_beyond_loopback(int(server.address.rsplit(":", 1)[1])):
                raise RuntimeError(f"jmeter server {server.address} listens beyond loopback - refusing to run")
        yield servers
    finally:
        for proc in procs:
            if proc.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM)
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)


def run_remote(plan: Path, servers: list[RemoteServer], gprops: dict[str, object], out_dir: Path,
               timeout: float = 90) -> tuple[Path, str]:
    """The controller: sends ``plan`` to every server, ``-G`` properties to all of them, collects the samples into
    one JTL and stops the servers at the end (``-X``). Returns the JTL path and the console output."""
    home = jmeter_home()
    out_dir.mkdir(parents=True, exist_ok=True)
    keystore = make_keystore(servers[0].dir.parent)
    jtl = out_dir / "results.jtl"
    jtl.unlink(missing_ok=True)
    cmd = [str(home / "bin" / "jmeter"), f"-Djava.rmi.server.hostname={HOST}", "-n", "-t", str(plan),
           "-R", ",".join(s.address for s in servers), *_ssl_props(keystore), "-l", str(jtl),
           "-j", str(out_dir / "controller.log"), "-X",
           "-Jjmeterengine.nongui.port=0",  # no UDP shutdown listener on all interfaces ("set the port to 1000 or less")
           *[f"-G{k}={v}" for k, v in gprops.items()]]
    proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=timeout, env=_env())
    if proc.returncode != 0 or not jtl.exists():
        raise RuntimeError(f"distributed run failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return jtl, proc.stdout
