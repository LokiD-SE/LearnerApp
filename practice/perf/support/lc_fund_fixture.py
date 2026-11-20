"""Fixtures for the Locust fundamentals lesson (tests/locust/test_lc_fund_*.py).

- ``load_exercise(relative)`` imports a Python exercise module from its file. The topic folder is called
  ``locust``, like the Locust package itself, so ``from locust.lc_fund_stats import ...`` would find the real
  package (and importing Locust inside pytest monkey-patches everything with gevent). Loading by path avoids both.
- ``SAMPLE_STATS`` is the --json-file output of a real 5-second Locust 2.47.0 run against the practice API
  (5 users, 40 ms +/- 30 ms service time, 10 % injected payment errors), captured on 20 November 2026 with
  floats rounded to 3 decimals. Only the fields the exercise reads are kept.
- ``write_locustfile(folder, name)`` writes one of the small locustfiles below into a temporary folder, so a test
  can run Locust on a known script in a subprocess.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from load_tools import practice_file


def load_exercise(relative: str) -> ModuleType:
    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_STATS: list[dict] = [{'method': 'POST', 'name': '/auth/token', 'num_requests': 5, 'num_none_requests': 0, 'num_failures': 0, 'total_response_time': 197.704, 'min_response_time': 19.688, 'max_response_time': 70.355, 'start_time': 1795190115.023, 'last_request_timestamp': 1795190115.076, 'response_times': {'20': 1, '29': 1, '37': 1, '41': 1, '70': 1}}, {'method': 'GET', 'name': '/v1/payments', 'num_requests': 82, 'num_none_requests': 0, 'num_failures': 0, 'total_response_time': 3319.167, 'min_response_time': 13.101, 'max_response_time': 73.199, 'start_time': 1795190115.052, 'last_request_timestamp': 1795190119.567, 'response_times': {'13': 2, '14': 1, '15': 1, '16': 3, '17': 1, '18': 2, '19': 3, '20': 3, '21': 2, '22': 1, '23': 1, '24': 2, '25': 4, '26': 2, '28': 1, '29': 1, '30': 2, '31': 2, '32': 2, '33': 2, '34': 1, '36': 2, '39': 1, '41': 2, '42': 1, '43': 2, '44': 2, '45': 1, '47': 1, '48': 3, '50': 2, '55': 2, '56': 1, '57': 1, '58': 1, '59': 1, '60': 2, '61': 1, '62': 3, '64': 1, '65': 1, '66': 1, '67': 1, '68': 2, '69': 3, '70': 1, '71': 2, '72': 1, '73': 1}}, {'method': 'GET', 'name': '/v1/reports/settlement', 'num_requests': 10, 'num_none_requests': 0, 'num_failures': 0, 'total_response_time': 4184.622, 'min_response_time': 237.494, 'max_response_time': 558.771, 'start_time': 1795190115.605, 'last_request_timestamp': 1795190119.491, 'response_times': {'240': 1, '300': 1, '370': 1, '390': 1, '400': 2, '490': 1, '510': 1, '530': 1, '560': 1}}, {'method': 'POST', 'name': '/v1/payments', 'num_requests': 36, 'num_none_requests': 0, 'num_failures': 5, 'total_response_time': 2873.652, 'min_response_time': 22.582, 'max_response_time': 142.155, 'start_time': 1795190115.622, 'last_request_timestamp': 1795190119.541, 'response_times': {'23': 1, '25': 1, '27': 1, '28': 2, '36': 1, '37': 1, '39': 1, '40': 1, '43': 2, '45': 1, '47': 1, '49': 1, '53': 1, '75': 1, '77': 1, '84': 1, '86': 1, '93': 1, '98': 1, '100': 2, '110': 4, '120': 4, '130': 3, '140': 2}}]

LOCUSTFILES = {
    # Logs in, then creates payments; with the target's error_rate some creations fail with 500.
    "payer": '''
import uuid

from locust import HttpUser, constant, task


class Payer(HttpUser):
    wait_time = constant(0.05)

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def create_payment(self):
        self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())})
''',
    # Never logs in, so every payment list fails with 401 - a run that must end with a failing exit code.
    "no_login": '''
from locust import HttpUser, constant, task


class Anonymous(HttpUser):
    wait_time = constant(0.1)

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=5", name="/v1/payments")
''',
    # Only the health check - a run with no failures.
    "healthy": '''
from locust import HttpUser, constant, task


class Prober(HttpUser):
    wait_time = constant(0.1)

    @task
    def health(self):
        self.client.get("/health")
''',
}


def write_locustfile(folder: Path, name: str) -> Path:
    path = folder / f"{name}_locustfile.py"
    path.write_text(LOCUSTFILES[name].lstrip())
    return path
