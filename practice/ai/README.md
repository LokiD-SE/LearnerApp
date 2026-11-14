# AI engineering practice project (Track J)

Python exercises for Track J (AI engineering): NumPy and pandas, the maths of machine learning, scikit-learn,
and later PyTorch, LLM applications, agents and the Model Context Protocol. Each exercise is checked by pytest
tests. Nothing calls a paid API: LLM and agent exercises run against a scripted fake model, so every test
passes offline and free.

- `exercises/<topic>/` - the files you change. They import cleanly but are unsolved.
- `solutions/<topic>/` - reference solutions at the same paths. Look only after you have tried.
- `tests/<topic>/test_*.py` - the tests that check your work. Every test file is an exercise; it marks its
  tests with `pytestmark = pytest.mark.exercise`.

You need **Python 3.12** (`python3 --version`; `.python-version` names it).

```bash
cd practice/ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ml_foundations/test_arrays.py   # one exercise; read the first failure
AI_TARGET=solutions .venv/bin/python -m pytest                    # every test against the solutions
.venv/bin/python scripts/verify.py                                # what CI runs: solutions pass, exercises fail
```

Tests import the code under test by topic (`from ml_foundations.arrays import ...`); `conftest.py` puts
`exercises/` (default) or `solutions/` (`AI_TARGET=solutions`) on the import path. Tests are deterministic:
they fix random seeds and compare floats with `pytest.approx` or `numpy.testing`.
