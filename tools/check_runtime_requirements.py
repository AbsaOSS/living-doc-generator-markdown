#
# Copyright 2025 ABSA Group Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
The guard that keeps `requirements.txt` free of test, lint and type tools; run by `make runtime-requirements`.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements.txt"

DENIED_NAMES = frozenset(
    {
        "bandit",
        "black",
        "coverage",
        "flake8",
        "isort",
        "mypy",
        "mypy-extensions",
        "nox",
        "pre-commit",
        "pylint",
        "pyright",
        "pytest",
        "pytype",
        "ruff",
        "tox",
        "faker",
        "freezegun",
        "hypothesis",
        "responses",
    }
)

DENIED_PREFIXES = ("pytest-", "types-", "mock", "flake8-")

# A plain PEP 508 requirement. An include, a flag, a VCS or URL reference or a local path does not match.
_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[A-Za-z0-9._,-]+\])?"
    r"(?:\s*(?:===|==|!=|~=|<=|>=|<|>)\s*[^;]+?)?"
    r"(?:\s*;.*)?$"
)

_SEPARATOR_RUN_RE = re.compile(r"[-_.]+")


def _normalize(name: str) -> str:
    """The distribution name as PEP 503 compares it."""
    return _SEPARATOR_RUN_RE.sub("-", name).lower()


def denied_requirements(requirements_path: Path) -> list[str]:
    """
    Every development tool a requirements file names, and every line that is not a plain requirement.

    @param requirements_path: The requirements file to read.
    @return: The offending names, or the whole line where no name can be read, in file order.
    """
    denied = []
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plain = _REQUIREMENT_RE.match(line)
        if plain is None:
            denied.append(line)
            continue
        name = _normalize(plain.group("name"))
        if name in DENIED_NAMES or name.startswith(DENIED_PREFIXES):
            denied.append(name)
    return denied


def main(requirements_path: Path = RUNTIME_REQUIREMENTS) -> int:
    """
    Report every denied requirement of the runtime requirements file.

    @param requirements_path: The file to check; defaults to `requirements.txt`.
    @return: 0 when the file is runtime-only, 1 otherwise.
    """
    denied = denied_requirements(requirements_path)
    if not denied:
        return 0
    print(
        f"{requirements_path.name} must name only runtime pins. Move a development tool to "
        f"requirements-dev.txt; replace an include or a URL/path reference with the pin itself:",
        file=sys.stderr,
    )
    for name in denied:
        print(f"  {name}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
