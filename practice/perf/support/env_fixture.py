"""Fixtures for the lesson "Test environments and test data" (prefix env_).

``serve_cold_start`` runs a tiny loopback-only server that is slow until its "cache" is warm: the first
``warm_after`` requests take ``cold_ms`` each, later ones ``warm_ms``. That imitates what a freshly deployed
service does (empty caches, connection pools still opening, JIT not compiled yet) so the steady-state exercise
has a real warm-up to find.

``WARMUP_PLAN`` is a JMeter plan (threads and loops set with -J properties) that loads it; ``write_plan``
writes it to a folder so ``load_tools.run_jmeter`` can run it.
"""

from __future__ import annotations

import contextlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


@contextlib.contextmanager
def serve_cold_start(warm_after: int = 200, cold_ms: float = 40.0, warm_ms: float = 5.0) -> Iterator[str]:
    lock = threading.Lock()
    count = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        # Headers and body are separate writes; without this, Nagle's algorithm plus the client's delayed ACK
        # add about 40 ms to every keep-alive response and hide the warm-up.
        disable_nagle_algorithm = True

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            with lock:
                count["n"] += 1
                n = count["n"]
            time.sleep((cold_ms if n <= warm_after else warm_ms) / 1000)
            body = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 256

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


WARMUP_PLAN = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Warm-up probe">
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Probe">
        <stringProp name="ThreadGroup.num_threads">${__P(threads,4)}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">0</stringProp>
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController">
          <stringProp name="LoopController.loops">${__P(loops,250)}</stringProp>
          <boolProp name="LoopController.continue_forever">false</boolProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="GET /health">
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.domain">127.0.0.1</stringProp>
          <stringProp name="HTTPSampler.port">${__P(port,8090)}</stringProp>
          <stringProp name="HTTPSampler.path">/health</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""


def write_plan(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "env_warmup.jmx"
    path.write_text(WARMUP_PLAN)
    return path
