# Performance testing practice project (Track K)

Load tests with **Apache JMeter 5.6.3** and **Locust 2.47.0**, plus Python exercises that model workloads and
analyse results. Everything runs against `support/sandpay_target.py`, a SandPay practice API on your own
machine (loopback only). Never point a load test at a system you do not own or have written permission to test.

- `exercises/<topic>/` - the files you change (Python modules, locustfiles, JMeter `.jmx` plans).
- `solutions/<topic>/` - reference solutions at the same paths. Look only after you have tried.
- `tests/<topic>/test_*.py` - the pytest tests that check your work; `pytestmark = pytest.mark.exercise`.
- `support/` - the practice API (`sandpay_target.py`) and helpers that run JMeter and Locust headless
  (`load_tools.py`). `tests/support/` checks those, not you.
- `tools/` - JMeter, downloaded by `scripts/get-jmeter.sh` (gitignored).

```bash
cd practice/perf
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
scripts/get-jmeter.sh                                  # needs Java 8+; JDK 17 and 21 are tested
.venv/bin/python -m pytest tests/support                # target, JMeter and Locust work
.venv/bin/python support/sandpay_target.py --port 8090  # the practice API, for exploring by hand
PERF_TARGET=solutions .venv/bin/python -m pytest        # every test against the solutions
.venv/bin/python scripts/verify.py                      # what CI runs: solutions pass, exercises fail
```

Load numbers depend on your machine, so tests check behaviour (which requests ran, which failed, which
assertion fired, how a model scales) rather than absolute response times.
