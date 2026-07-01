"""Repo-root conftest.

Its only job is to exist: pytest inserts the directory of the root conftest into
``sys.path`` at startup, so ``from tests.conftest import ...`` and
``from tests.generators import ...`` resolve under the bare ``pytest`` console
command used in CI (which, unlike ``python -m pytest``, does not add the current
directory to ``sys.path``).
"""
