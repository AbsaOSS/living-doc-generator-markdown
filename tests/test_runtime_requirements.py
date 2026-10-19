#
# Copyright 2026 ABSA Group Limited
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
import pytest

from tools.check_runtime_requirements import denied_requirements, main


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("pytest==9.1.1", "pytest"),
        ("pytest-cov==7.1.0", "pytest-cov"),
        ("black==26.5.1", "black"),
        ("mypy==2.3.1", "mypy"),
        ("ruff==0.16.9", "ruff"),
        ("types-requests==2.33.0", "types-requests"),
        ("pyright==1.1.0", "pyright"),
        ("hypothesis==6.0.0", "hypothesis"),
        # PEP 503: pip installs the same distribution for every spelling.
        ("PyTest==9.1.1", "pytest"),
        ("pytest_cov==7.1.0", "pytest-cov"),
        ("pytest.cov==7.1.0", "pytest-cov"),
        ("pytest..cov==7.1.0", "pytest-cov"),
        ("mypy.extensions==1.1.0", "mypy-extensions"),
    ],
)
def test_a_development_tool_in_the_runtime_file_is_reported(tmp_path, line, expected):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"living-doc-utilities==0.6.0\n{line}\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == [expected]
    assert main(planted) == 1


@pytest.mark.parametrize(
    "line",
    [
        "-r requirements-dev.txt",
        "--requirement requirements-dev.txt",
        "git+https://github.com/psf/black@main",
        "https://example.invalid/pytest-9.1.1-py3-none-any.whl",
        "./wheels/pytest-9.1.1-py3-none-any.whl",
    ],
)
def test_a_line_naming_no_plain_requirement_is_reported(tmp_path, line):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"living-doc-utilities==0.6.0\n{line}\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == [line]
    assert main(planted) == 1


@pytest.mark.parametrize(
    "line",
    [
        "living-doc-utilities==0.6.0",
        'tomli==2.4.1; python_version < "3.11"',
        "living-doc-utilities[html]==0.6.0",
        "living-doc-utilities>=0.6.0,<0.7",
        "pydantic ~= 2.13",
    ],
)
def test_a_plain_runtime_pin_is_not_reported(tmp_path, line):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"{line}\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == []
    assert main(planted) == 0


def test_a_commented_out_development_tool_is_not_reported(tmp_path):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text("living-doc-utilities==0.6.0\n# pytest==9.1.1\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == []
