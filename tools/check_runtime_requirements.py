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
The guard that keeps `requirements.txt` a runtime-only file: the action installs it into its own venv on
every run, so a test, lint or type tool named there is downloaded on every run of every caller. Those
tools belong in `requirements-dev.txt`. Run by `make qa`; exits 1 and names each offender.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Names no runtime requirements file may carry, each a test runner, linter, formatter or type checker.
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
        # Test helpers: only a test suite has a reason to fake data, time or HTTP.
        "faker",
        "freezegun",
        "hypothesis",
        "responses",
    }
)

# Families of the same kind: a pytest plugin, a type-stub distribution, or any other mock helper.
DENIED_PREFIXES = ("pytest-", "pytest_", "types-", "types_", "mock", "flake8-")

# A requirement line's distribution name: everything before the first extra, marker, version or URL separator.
_NAME_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)")

# A whole plain PEP 508 requirement and nothing else: a name, optional extras, an optional version specifier
# and an optional environment marker. Anything that does not match in full - an `-r` include, a bare `--flag`,
# a `git+`/`https://` reference, a local path or wheel - names no distribution this check can judge.
_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[A-Za-z0-9._,-]+\])?"
    r"(?:\s*(?:===|==|!=|~=|<=|>=|<|>)\s*[^;]+?)?"
    r"(?:\s*;.*)?$"
)


# PEP 503: a run of `-`, `_` or `.` is one `-`, so `pytest.cov`, `pytest_cov` and `pytest-cov` are the same
# distribution to pip - and must be the same name to the deny list.
_SEPARATOR_RUN_RE = re.compile(r"[-_.]+")


def _normalize(name: str) -> str:
    """The distribution name lowercased, with every run of `-`, `_` or `.` folded to one `-` (PEP 503)."""
    return _SEPARATOR_RUN_RE.sub("-", name).lower()


def requirement_name(line: str) -> str:
    """
    The distribution a requirement line names, lowercased with `_` folded to `-` (PEP 503).

    @param line: One line of a requirements file, already stripped of its comment.
    @return: The distribution name, or an empty string for a line that names none (`-r`, `--flag`, blank).
    """
    name_m = _NAME_RE.match(line.strip())
    return _normalize(name_m.group("name")) if name_m else ""


def denied_requirements(requirements_path: Path) -> list[str]:
    """
    Every line of a requirements file that a runtime-only file may not carry.

    A named test, lint or type tool is one case. The other is a line this check cannot read as a plain
    PEP 508 requirement - an `-r`/`--requirement` include, a VCS or URL reference, a local path or wheel.
    Those are reported too rather than skipped: an include pulls in whatever the other file names (and
    `requirements-dev.txt` includes this one, so inverting the two is an easy mistake), and `git+...` or
    `./dist/x.whl` hides the distribution's real name from the deny list. A runtime file naming its own
    pins outright never trips this.

    @param requirements_path: The runtime requirements file to read.
    @return: The offending names, or the whole offending line where no name can be read, in file order.
    """
    denied = []
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plain = _REQUIREMENT_RE.match(line)
        if plain is None:
            # Nothing a deny list can be applied to: report the line and let a human judge it.
            denied.append(line)
            continue
        name = _normalize(plain.group("name"))
        if name in DENIED_NAMES or name.startswith(DENIED_PREFIXES):
            denied.append(name)
    return denied


def main(requirements_path: Path = RUNTIME_REQUIREMENTS) -> int:
    """
    Report every denied requirement of the runtime requirements file.

    @param requirements_path: The file to check; defaults to this repository's `requirements.txt`. A test
                              passes its own so the reporting path is exercised, not only the clean one.
    @return: The process exit code: 0 when the file is runtime-only, 1 otherwise.
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
