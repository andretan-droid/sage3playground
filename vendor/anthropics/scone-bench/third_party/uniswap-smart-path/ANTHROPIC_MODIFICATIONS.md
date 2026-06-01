# Modifications to uniswap-smart-path

This directory vendors [Elnaril/uniswap-smart-path](https://github.com/Elnaril/uniswap-smart-path) (MIT License).

Anthropic-authored additions (Apache-2.0, © 2026 Anthropic PBC):

- `uniswap_smart_path/cli.py` — a thin CLI wrapper so the model can invoke
  path-finding from bash.

Upstream files removed for size: `.github/`, `tests/`, `integration_tests/`,
`media/`, `coverage.json`, `uv.lock`, `tox.ini`, `mypy.ini`, `pytest.ini`,
`requirements*.txt`. Runtime install reads `pyproject.toml` only.
