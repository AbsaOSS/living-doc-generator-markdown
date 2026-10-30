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
"""
The promises of `local-integration.sh`, an operator's run of the generator over given `living-doc-toolkit` outputs
outside any workflow, and of `tools/local_integration.py`, its Python half: every document is checked against its input
re-read with `read_artifact`, and reported; the configuration is read as data and never sourced; a misconfiguration or a
failed step stops the run with one actionable stderr line; no token reaches anything the script prints, starts or
writes; and no workflow runs it.

The script runs end to end here in a copy whose venv is seeded: its interpreter is this test's, which has the packages
installed already, so the run builds no venv and needs no network. Everything after the install runs for real.
"""

import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Optional

import pytest
from living_doc_utilities.contracts import coverage_matrix, doc_source, generator_ready, ui_test_catalog
from living_doc_utilities.contracts.envelope import ContractWarning
from living_doc_utilities.contracts.io import read_artifact, write_artifact
from living_doc_utilities.contracts.testing import full_sample

from generator_markdown.source_reader import CONTRACT_NAMES
from main import run as render_document
from tools.local_integration import CONTRACTS, FIRST_OCCURRENCES, NotRendered, main, report, warnings_by_code

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "local-integration.sh"
EXAMPLE_CONFIG = REPO_ROOT / ".env.local.example"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Per document type, in the order the script renders them: the contract id of the input it renders.
INPUTS = {
    "technical-project": generator_ready.CONTRACT_ID,
    "ui-test-catalog": ui_test_catalog.CONTRACT_ID,
    "coverage-matrix": coverage_matrix.CONTRACT_ID,
}

# The command that writes the example's inputs, which no commit holds.
SAMPLES_COMMAND = "python3 tools/write_sample_inputs.py output/samples generator-ready ui-test-catalog coverage-matrix"

# A token-shaped value no real credential has; the script must print it nowhere, hand it to no child and write it to
# no output.
TOKEN = "ghp_dummy_local_integration_token"


def _contract_name(contract_id: str) -> str:
    return contract_id.rsplit("-v", 1)[0]


def test_the_helpers_contract_table_is_the_generators():
    # Assert: the helper keeps its own copy, as its venv cannot import the generator it checks.
    assert CONTRACTS == {document_type.value: name for document_type, name in CONTRACT_NAMES.items()}
    assert CONTRACTS == {document_type: _contract_name(contract_id) for document_type, contract_id in INPUTS.items()}


def test_the_helper_imports_living_doc_utilities_and_the_standard_library_alone():
    # Arrange
    tree = ast.parse((REPO_ROOT / "tools" / "local_integration.py").read_text(encoding="utf-8"))
    modules = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    modules |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}

    # Assert: the script's venv holds `requirements.txt` alone, and the check stays apart from `generator_markdown`.
    assert modules
    assert {
        module for module in modules if module.split(".")[0] not in {"living_doc_utilities", *sys.stdlib_module_names}
    } == set()


# --- warnings by code ----------------------------------------------------------------------------------------------


def _warning(message: str, code: str = "MALFORMED_AC", **where) -> ContractWarning:
    return ContractWarning(code=code, message=message, **where)


def test_no_warnings_is_the_header_alone():
    # Act & Assert
    assert warnings_by_code([]) == ["  warnings: 0"]


def test_warnings_are_grouped_by_sorted_code_each_in_input_order():
    # Arrange
    warnings = [
        _warning("z first", code="ZETA_CODE"),
        _warning("a only", code="ALPHA_CODE"),
        _warning("z second", code="ZETA_CODE"),
    ]

    # Act & Assert
    assert warnings_by_code(warnings) == [
        "  warnings: 3",
        "    ALPHA_CODE: 1",
        "      - a only",
        "    ZETA_CODE: 2",
        "      - z first",
        "      - z second",
    ]


def test_ten_occurrences_of_a_code_are_listed_and_the_rest_counted():
    # Arrange
    warnings = [_warning(f"w{n:02d}") for n in range(12)] + [_warning("ten", code="TEN")] * 10

    # Act & Assert: a code with exactly ten is listed whole.
    assert FIRST_OCCURRENCES == 10
    assert warnings_by_code(warnings) == [
        "  warnings: 22",
        "    MALFORMED_AC: 12",
        *(f"      - w{n:02d}" for n in range(10)),
        "      ... and 2 more",
        "    TEN: 10",
        *["      - ten"] * 10,
    ]


@pytest.mark.parametrize(
    ("where", "expected"),
    [
        (
            {"path": "us/loans.md", "line_no": 12, "entity_id": "US-7", "ac_id": "US-7-02"},
            "us/loans.md:12 US-7/US-7-02 msg",
        ),
        (
            {"context": "source_input='doc-source-v1.0.0'", "entity_id": "FEAT-3"},
            "source_input='doc-source-v1.0.0' FEAT-3 msg",
        ),
        ({"path": "us/loans.md", "context": "not shown when a path is known"}, "us/loans.md msg"),
        ({}, "- msg"),
    ],
    ids=["everything", "context", "path-over-context", "none"],
)
def test_an_occurrence_says_where_and_about_what(where, expected):
    # Act & Assert: `<path or context or ->[:line] <entity>/<ac> <message>`, empty parts dropped.
    assert warnings_by_code([_warning("msg", **where)]) == ["  warnings: 1", "    MALFORMED_AC: 1", f"      {expected}"]


# --- report: one document checked against its input ----------------------------------------------------------------


def _render(monkeypatch, document_type: str, source: Path, output: Path) -> None:
    """Render one document as the action runs `main.py`: its three inputs, no title."""
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", document_type)
    monkeypatch.setenv("INPUT_SOURCE_PATH", os.fspath(source))
    monkeypatch.setenv("INPUT_OUTPUT_PATH", os.fspath(output))
    render_document()


@pytest.fixture(name="rendered")
def _rendered(tmp_path, write_sample, monkeypatch) -> dict[str, tuple[str, str]]:
    """Per document type: its sample input, and the directory `main.py` rendered the document into."""
    output = tmp_path / "out"
    rendered = {}
    for document_type, contract_id in INPUTS.items():
        source = write_sample(contract_id, f"{_contract_name(contract_id)}.json")
        _render(monkeypatch, document_type, source, output)
        rendered[document_type] = (os.fspath(source), os.fspath(output))
    return rendered


def _run_report_of(output: str, document_type: str) -> Path:
    return Path(output) / f"{document_type}.run-report.json"


def test_the_report_describes_the_document_its_input_and_its_run_report(rendered):
    # Arrange
    source_path, output = rendered["technical-project"]
    source = read_artifact(source_path, "generator-ready")
    producer = source.metadata.producer
    document = Path(output) / "technical-project.md"
    run_report_path = _run_report_of(output, "technical-project")
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    manifest = run_report["render_manifest"]

    # Act
    lines = report("technical-project", source_path, output, 1234)

    # Assert: what was rendered from what, the view and title it was rendered with, the time and the sizes.
    assert lines[:7] == [
        f"technical-project: {output}{os.sep}technical-project.md",
        "  input: generator-ready-v1.0.0, valid (read_artifact)",
        f"  producer: {producer.name} {producer.version}, living-doc-utilities {producer.utilities_version}",
        "  view: inner",
        f"  title: {run_report['title']}",
        "  time: 1.23 s",
        f"  size: {document.stat().st_size} bytes, run report {run_report_path.stat().st_size} bytes",
    ]
    # Assert: the run report's counts, a mapping as sorted pairs, then the length of each manifest list.
    manifest_at = lines.index("  render_manifest:")
    assert lines[7:manifest_at] == [
        "  counts:",
        "    entities: 9",
        "    entities_by_type: DocumentedFeature=3, DocumentedFunctionality=3, DocumentedUserStory=3",
        "    acceptance_criteria: 11",
        "    scenarios: 0",
        "    warnings_by_code: MALFORMED_AC=1, MISSING_ENTITY_ID=1, UNPARSED_AC_LINE=1",
    ]
    assert lines[manifest_at + 1 : manifest_at + 7] == [
        "    entities: 9",
        "    acceptance_criteria: 11",
        f"    aspects: {len(manifest['aspects'])}",
        f"    badges: {len(manifest['badges'])}",
        "    scenarios: 0",
        "    not_loaded: 3",
    ]
    # Assert: the input's warnings, by code.
    assert lines[manifest_at + 7 :] == warnings_by_code(source.warnings)
    assert lines[manifest_at + 7] == "  warnings: 3"


def test_the_coverage_matrix_manifest_lists_every_counted_entity_and_criterion(rendered):
    # Act
    lines = report("coverage-matrix", *rendered["coverage-matrix"], 0)

    # Assert
    counts_at = lines.index("  counts:")
    manifest_at = lines.index("  render_manifest:")
    assert lines[counts_at + 1] == lines[manifest_at + 1] == "    entities: 6"
    assert lines[counts_at + 3] == lines[manifest_at + 2] == "    acceptance_criteria: 7"


def test_the_catalog_is_not_held_to_the_manifest_check(rendered):
    # Act
    lines = report("ui-test-catalog", *rendered["ui-test-catalog"], 0)

    # Assert: its counts hold no entity or criterion, and count a scenario in each group; its manifest lists each
    # entity and scenario once.
    counts_at = lines.index("  counts:")
    manifest_at = lines.index("  render_manifest:")
    assert lines[counts_at + 1 : manifest_at] == [
        "    entities: 0",
        "    entities_by_type: -",
        "    acceptance_criteria: 0",
        "    scenarios: 6",
        "    warnings_by_code: -",
    ]
    assert lines[manifest_at + 1] == "    entities: 2"
    assert lines[manifest_at + 5] == "    scenarios: 2"
    assert lines[-1] == "  warnings: 0"


@pytest.mark.parametrize(("elapsed_ms", "shown"), [(0, "0.00"), (125600, "125.60")])
def test_the_time_is_shown_in_seconds_to_two_decimals(rendered, elapsed_ms, shown):
    # Act & Assert
    assert report("ui-test-catalog", *rendered["ui-test-catalog"], elapsed_ms)[5] == f"  time: {shown} s"


def test_main_prints_the_report_and_exits_zero(rendered, capsys):
    # Arrange
    source_path, output = rendered["coverage-matrix"]

    # Act
    code = main(["report", "coverage-matrix", source_path, output, "1234"])

    # Assert
    out, err = capsys.readouterr()
    assert code == 0
    assert err == ""
    assert out == "\n".join(report("coverage-matrix", source_path, output, 1234)) + "\n"


def _main_fails(capsys, document_type: str, source_path: str, output: str) -> str:
    """Run `main` on one document, expecting the one-line failure; return that line."""
    code = main(["report", document_type, source_path, output, "5"])
    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    [line] = err.splitlines()
    return line


@pytest.mark.parametrize(
    ("which", "content", "says"),
    [
        ("md", None, "the document '{path}' is missing"),
        ("md", "", "the document '{path}' is empty"),
        ("run-report.json", None, "the run report '{path}' is missing"),
        ("run-report.json", "", "the run report '{path}' is empty"),
        ("run-report.json", "{ not json", "the run report '{path}' is not JSON: "),
        ("run-report.json", "{}", "the run report '{path}' holds no counts or no render manifest"),
        (
            "run-report.json",
            '{"counts": {}, "render_manifest": {}}',
            "the run report '{path}' holds no counts or no render manifest",
        ),
    ],
    ids=[
        "document-missing",
        "document-empty",
        "missing",
        "empty",
        "not-json",
        "empty-object",
        "manifest-without-lists",
    ],
)
def test_a_missing_or_empty_document_or_run_report_fails_with_one_line(rendered, capsys, which, content, says):
    # Arrange
    source_path, output = rendered["technical-project"]
    path = Path(output) / f"technical-project.{which}"
    if content is None:
        path.unlink()
    else:
        path.write_text(content, encoding="utf-8")

    # Act & Assert
    with pytest.raises((NotRendered, OSError)):
        report("technical-project", source_path, output, 5)
    assert _main_fails(capsys, "technical-project", source_path, output).startswith(
        f"technical-project: {says.format(path=os.path.join(output, path.name))}"
    )


def _edit_run_report(output: str, document_type: str, edit) -> None:
    path = _run_report_of(output, document_type)
    run_report = json.loads(path.read_text(encoding="utf-8"))
    edit(run_report)
    path.write_text(json.dumps(run_report), encoding="utf-8")


@pytest.mark.parametrize(
    ("edit", "says"),
    [
        (
            lambda r: r["counts"].update(entities=10),
            "the run report's counts differ from the input's metadata.stats.cardinality: entities 10, the input's 9",
        ),
        (
            lambda r: r["counts"]["warnings_by_code"].pop("MALFORMED_AC"),
            "the run report's counts differ from the input's metadata.stats.cardinality: warnings_by_code "
            "MISSING_ENTITY_ID=1, UNPARSED_AC_LINE=1, the input's MALFORMED_AC=1, MISSING_ENTITY_ID=1, "
            "UNPARSED_AC_LINE=1",
        ),
        (
            lambda r: r["counts"].pop("scenarios"),
            "the run report's counts differ from the input's metadata.stats.cardinality: scenarios -, the input's 0",
        ),
        (
            lambda r: r.update(view="release"),
            "the run report's view is 'release', its manifest's 'inner'; the input's is 'inner'",
        ),
        (
            lambda r: r["render_manifest"].update(view="release"),
            "the run report's view is 'inner', its manifest's 'release'; the input's is 'inner'",
        ),
    ],
    ids=["count", "warnings-by-code", "count-absent", "view", "manifest-view"],
)
def test_a_run_report_whose_counts_or_view_differ_from_the_input_fails(rendered, capsys, edit, says):
    # Arrange
    source_path, output = rendered["technical-project"]
    _edit_run_report(output, "technical-project", edit)

    # Act & Assert
    with pytest.raises(NotRendered):
        report("technical-project", source_path, output, 5)
    assert _main_fails(capsys, "technical-project", source_path, output) == f"technical-project: {says}"


@pytest.mark.parametrize("document_type", ["technical-project", "coverage-matrix"])
@pytest.mark.parametrize("listed", ["entities", "acceptance_criteria"])
def test_a_manifest_that_lists_other_than_the_counts_fails(rendered, capsys, document_type, listed):
    # Arrange: one entry fewer than the counts hold.
    source_path, output = rendered[document_type]
    _edit_run_report(output, document_type, lambda r: r["render_manifest"][listed].pop())
    counted = json.loads(_run_report_of(output, document_type).read_text(encoding="utf-8"))["counts"][listed]

    # Act & Assert
    assert _main_fails(capsys, document_type, source_path, output) == (
        f"{document_type}: the render manifest lists {counted - 1} {listed} where the run report counts {counted}"
    )


def test_a_catalog_manifest_that_lists_other_than_the_counts_passes(rendered, capsys):
    # Arrange
    source_path, output = rendered["ui-test-catalog"]
    _edit_run_report(output, "ui-test-catalog", lambda r: r["render_manifest"].update(entities=[], scenarios=[]))

    # Act & Assert
    assert main(["report", "ui-test-catalog", source_path, output, "5"]) == 0
    assert capsys.readouterr().err == ""


def test_an_input_of_another_contract_fails_with_one_line(rendered, capsys):
    # Arrange: the catalog's input where the technical project's belongs.
    source_path, _ = rendered["ui-test-catalog"]
    _, output = rendered["technical-project"]

    # Act & Assert
    assert _main_fails(capsys, "technical-project", source_path, output) == (
        "technical-project: the input is not valid: [CONTRACT_MISMATCH] expected one of ['generator-ready'], "
        "got 'ui-test-catalog'"
    )


def test_main_spells_out_the_control_characters_a_file_carries(tmp_path, monkeypatch, capsys):
    # Arrange: an input whose title and one warning would clear the terminal and forge a report line.
    sample = full_sample(generator_ready.CONTRACT_ID)
    crafted = sample.model_copy(
        update={
            "document": sample.document.model_copy(update={"title": "\x1b[2J\n  view: release"}),
            "warnings": [*sample.warnings, _warning("\x1b]0;x\x07\n  warnings: 0")],
        }
    )
    source = tmp_path / "generator-ready.json"
    write_artifact(crafted, source)
    output = tmp_path / "out"
    _render(monkeypatch, "technical-project", source, output)

    # Act
    code = main(["report", "technical-project", os.fspath(source), os.fspath(output), "5"])

    # Assert: each value stays on its own line, its control characters spelled out.
    out, _ = capsys.readouterr()
    assert code == 0
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "  view: release" not in out.splitlines()
    assert "  warnings: 0" not in out.splitlines()
    assert "  title: \\x1b[2J\\n  view: release" in out.splitlines()
    assert "\\x1b]0;x\\x07\\n  warnings: 0" in out


# --- static promises over the script and its configuration --------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", os.fspath(REPO_ROOT), *args], capture_output=True, check=False, text=True, timeout=60
    )


def _shell_code() -> list[str]:
    """The script's lines without comments: in bash a `#` that starts a word starts a comment."""
    return [re.sub(r"(?:^|\s)#.*", "", line).strip() for line in SCRIPT.read_text(encoding="utf-8").splitlines()]


def _script_list(name: str) -> list[str]:
    """A whitespace-separated list the script assigns in double quotes, e.g. `KEYS`."""
    match = re.search(rf'^{name}="([^"]*)"', SCRIPT.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{name} is not assigned in {SCRIPT.name}"
    return match.group(1).split()


def _example_settings() -> dict[str, str]:
    settings = {}
    for line in EXAMPLE_CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, separator, value = line.partition("=")
            assert separator, f"not a KEY=value line in {EXAMPLE_CONFIG.name}: {line!r}"
            settings[key] = value
    return settings


def _action_venv_step() -> str:
    return (REPO_ROOT / "action.yml").read_text(encoding="utf-8")


def test_the_script_is_committed_executable():
    # Assert: `./local-integration.sh` runs on a fresh clone with no `chmod`.
    entry = _git("ls-files", "-s", SCRIPT.name).stdout
    assert entry.startswith("100755 "), f"{SCRIPT.name} is not committed with mode 100755: {entry!r}"


def test_the_script_keeps_lf_line_ends_on_every_checkout():
    # Assert: bash, Git Bash on Windows included, fails on a CRLF line.
    assert _git("check-attr", "eol", "--", SCRIPT.name).stdout.strip() == f"{SCRIPT.name}: eol: lf"
    assert b"\r" not in SCRIPT.read_bytes()


def test_no_workflow_runs_the_script():
    # Arrange
    workflows = [path for path in WORKFLOWS.rglob("*") if path.is_file()]

    # Assert: the script is an operator's tool; CI keeps `integration_test.yml`.
    assert workflows
    assert [
        path.name for path in workflows if re.search(r"local[-_]integration", path.read_text(encoding="utf-8"))
    ] == []


def test_the_example_documents_exactly_the_settings_the_script_reads():
    # Assert: a setting added to the script is added to the example the operator copies, and the example names
    # nothing else - no token.
    assert set(_example_settings()) == set(_script_list("KEYS"))


def test_the_example_renders_the_samples_its_comment_says_how_to_write():
    # Arrange
    required = _script_list("REQUIRED")
    example = _example_settings()

    # Assert: a copied example passes the required-key check, and reads the samples the named command writes.
    assert required == ["TECHNICAL_PROJECT_INPUT", "UI_TEST_CATALOG_INPUT", "COVERAGE_MATRIX_INPUT"]
    assert set(required) <= set(_script_list("KEYS"))
    assert [example[key] for key in required] == [
        f"output/samples/{_contract_name(contract_id)}.json" for contract_id in INPUTS.values()
    ]
    assert f"#   {SAMPLES_COMMAND}" in EXAMPLE_CONFIG.read_text(encoding="utf-8").splitlines()


def test_the_only_install_is_the_runtime_requirements_into_the_scripts_venv():
    # Assert: pip is always the venv's own, and installs `requirements.txt` alone - what the action installs.
    installs = [line for line in _shell_code() if re.search(r"\bpip\b", line) and re.search(r"\binstall\b", line)]
    assert installs == ['run "$VPY" -m pip install --disable-pip-version-check -r requirements.txt']
    assert "requirements-dev" not in SCRIPT.read_text(encoding="utf-8")


def test_the_script_unsets_the_pip_variables_and_checks_the_import_as_action_yml_does():
    # Arrange
    action = _action_venv_step()
    [unset] = [line.strip() for line in action.splitlines() if line.strip().startswith("unset PIP_")]
    [imports] = re.findall(r"-E -c '(import [^']+)'", action)

    # Assert: the install lands in the venv as the action's does (DEVELOPER.md § Action venv).
    assert unset in _shell_code()
    assert f"run \"$VPY\" -E -c '{imports}' \\" in _shell_code()


def test_the_script_never_sources_or_evaluates_a_file():
    # Arrange: the first word of every command, a line split at `;`, `&&` and `||`.
    commands = [
        segment.split()[0] for line in _shell_code() for segment in re.split(r";|&&|\|\|", line) if segment.split()
    ]

    # Assert: `.env.local` is read as data; a sourced file runs whatever it holds and exports any token in it.
    assert commands
    assert {"source", ".", "eval"} & set(commands) == set()


@pytest.mark.parametrize(
    "path", [".env.local", ".venv-local-integration/x", "output/generator-markdown/x"], ids=["config", "venv", "output"]
)
def test_what_the_script_reads_and_writes_locally_is_git_ignored(path):
    # Assert
    assert _git("check-ignore", "-q", "--no-index", path).returncode == 0, f"{path} is not git-ignored"


def test_the_example_config_is_not_git_ignored():
    # Assert: the pattern for `.env.local` does not swallow the committed example.
    assert _git("check-ignore", "-q", "--no-index", EXAMPLE_CONFIG.name).returncode == 1


# --- the script's behaviour, run with bash in a copy ---------------------------------------------------------------


def _bash() -> Optional[str]:
    """bash to run the script with: Git Bash on Windows, never `System32\\bash.exe`, the WSL launcher."""
    bash = shutil.which("bash")
    if bash and sys.platform == "win32" and "system32" in (part.lower() for part in Path(bash).parts):
        return None
    return bash


BASH = _bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no bash to run local-integration.sh with (Git Bash on Windows)")

# Process start-up is slow on Git Bash for Windows; a `--check` there takes seconds, a run tens of seconds.
TIMEOUT = 300


def _valid_config() -> dict[str, str]:
    """The example as committed, its interpreter this test's; the `workspace` fixture writes the samples it reads."""
    return {**_example_settings(), "PYTHON": Path(sys.executable).as_posix()}


@pytest.fixture(name="workspace")
def _workspace(tmp_path, write_sample):
    """A copy of the script in a directory of its own, the samples the example reads written under `output/samples/`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copyfile(SCRIPT, repo / SCRIPT.name)
    for contract_id in INPUTS.values():
        write_sample(contract_id, f"repo/output/samples/{_contract_name(contract_id)}.json")
    return repo


def _write_config(repo: Path, config: dict, extra_lines: tuple = ()) -> None:
    lines = [*(f"{key}={value}" for key, value in config.items()), *extra_lines]
    (repo / ".env.local").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _executable(path: Path, body: str) -> str:
    """A `/bin/sh` script at `path`, executable; its path as `.env.local`'s `PYTHON` takes it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8", newline="\n")
    path.chmod(0o755)
    return path.as_posix()


def _run(repo: Path, *args: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    assert BASH is not None
    return subprocess.run(
        [BASH, f"./{SCRIPT.name}", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
        check=False,
    )


def _files(directory: Path) -> list[str]:
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file())


SAMPLE_FILES = sorted(f"output/samples/{_contract_name(contract_id)}.json" for contract_id in INPUTS.values())


@needs_bash
def test_check_passes_on_a_valid_configuration_and_builds_nothing(workspace):
    # Arrange
    _write_config(workspace, _valid_config())

    # Act
    result = _run(workspace, "--check")

    # Assert: one line naming the Python found; no venv, no output, nothing else written.
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.startswith(f"local-integration.sh: check passed - Python {platform.python_version()} ")
    assert len(result.stdout.splitlines()) == 1
    assert _files(workspace) == sorted([".env.local", SCRIPT.name, *SAMPLE_FILES])


@needs_bash
def test_the_config_reads_comments_blank_lines_export_quotes_and_crlf(workspace):
    # Arrange: `.env.local` as an editor on Windows may leave it - CRLF line ends and no final one.
    config = _valid_config()
    lines = [
        "# a comment",
        "",
        *(f"{key}={value}" for key, value in config.items() if not key.endswith("_INPUT")),
        f'export TECHNICAL_PROJECT_INPUT="{config["TECHNICAL_PROJECT_INPUT"]}"',
        f"  UI_TEST_CATALOG_INPUT='{config['UI_TEST_CATALOG_INPUT']}'   ",
        f"COVERAGE_MATRIX_INPUT={config['COVERAGE_MATRIX_INPUT']}",
    ]
    (workspace / ".env.local").write_bytes("\r\n".join(lines).encode("utf-8"))

    # Act
    result = _run(workspace, "--check")

    # Assert
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "check passed" in result.stdout


@needs_bash
@pytest.mark.parametrize(
    ("setting", "says"),
    [
        ({"TECHNICAL_PROJECT_INPUT": None}, "TECHNICAL_PROJECT_INPUT is not set in .env.local"),
        ({"UI_TEST_CATALOG_INPUT": ""}, "UI_TEST_CATALOG_INPUT is not set in .env.local"),
        ({"COVERAGE_MATRIX_INPUT": "output/samples/missing.json"}, "COVERAGE_MATRIX_INPUT not found: "),
        ({"TECHNICAL_PROJECT_INPUT": "output/samples"}, "TECHNICAL_PROJECT_INPUT is not a file: "),
        ({"OUT_DIR": "output/samples/coverage-matrix.json"}, "OUT_DIR is not a directory: "),
    ],
    ids=["absent", "empty", "missing-input", "input-not-a-file", "output-a-file"],
)
def test_a_misconfiguration_fails_with_one_line_naming_it(workspace, setting, says):
    # Arrange
    config = {**_valid_config(), **setting}
    _write_config(workspace, {key: value for key, value in config.items() if value is not None})

    # Act
    result = _run(workspace, "--check")

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    [line] = result.stderr.splitlines()
    assert line.startswith(f"local-integration.sh: {says}")


@needs_bash
@pytest.mark.parametrize("args", [["--check"], []], ids=["check", "run"])
@pytest.mark.parametrize("reached", ["directly", "through-a-directory-symlink", "through-a-file-symlink"])
def test_an_input_in_the_directory_the_run_clears_fails_with_one_line_and_is_kept(workspace, tmp_path, args, reached):
    # Arrange: the technical project's input inside the generator's output directory, which a run clears first.
    kept = workspace / "output" / "generator-markdown" / "generator-ready.json"
    kept.parent.mkdir(parents=True)
    shutil.copyfile(workspace / "output" / "samples" / "generator-ready.json", kept)
    technical_project_input = "./output/generator-markdown/generator-ready.json"
    if reached != "directly":
        # A relative file link, as `ln -s` makes one: it resolves against the directory it is in.
        link, target = (
            (tmp_path / "link", kept.parent)
            if reached == "through-a-directory-symlink"
            else (tmp_path / "generator-ready.json", Path("repo/output/generator-markdown/generator-ready.json"))
        )
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError:
            pytest.skip("this file system or user cannot create a symlink")
        technical_project_input = (
            "../link/generator-ready.json" if reached == "through-a-directory-symlink" else "../generator-ready.json"
        )
    _write_config(workspace, {**_valid_config(), "TECHNICAL_PROJECT_INPUT": technical_project_input})

    # Act
    result = _run(workspace, *args)

    # Assert: one line naming it, before anything is built or cleared.
    assert result.returncode == 1
    [line] = result.stderr.splitlines()
    assert line.startswith("local-integration.sh: TECHNICAL_PROJECT_INPUT is in the directory the run clears: ")
    assert kept.exists()
    assert not (workspace / ".venv-local-integration").exists()


@needs_bash
@pytest.mark.parametrize("directory", [".", "generator-markdown-old"], ids=["output-root", "sibling"])
def test_an_input_under_the_output_but_outside_the_cleared_directory_passes_the_check(workspace, directory):
    # Arrange: only `generator-markdown/` is cleared; its parent and a sibling with a longer name are not.
    (workspace / "output" / "generator-markdown").mkdir()
    kept = workspace / "output" / directory / "kept-generator-ready.json"
    kept.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(workspace / "output" / "samples" / "generator-ready.json", kept)
    _write_config(
        workspace, {**_valid_config(), "TECHNICAL_PROJECT_INPUT": f"./output/{directory}/kept-generator-ready.json"}
    )

    # Act
    result = _run(workspace, "--check")

    # Assert
    assert result.returncode == 0, result.stderr
    assert "check passed" in result.stdout


@needs_bash
@pytest.mark.parametrize(("python", "says"), [("missing", "does not run"), ("3.9", "is 3.9.18")])
def test_a_python_that_does_not_run_or_is_older_than_3_10_fails_with_one_line(workspace, tmp_path, python, says):
    # Arrange: no file at all, or a Python 3.9 - it prints its version when asked and fails every other check.
    if python == "missing":
        interpreter = (tmp_path / "no-such-python").as_posix()
    else:
        interpreter = _executable(
            tmp_path / "python3.9", 'case "$2" in\n  *print*) echo 3.9.18 ;;\n  *) exit 1 ;;\nesac\n'
        )
    _write_config(workspace, {**_valid_config(), "PYTHON": interpreter})

    # Act
    result = _run(workspace, "--check")

    # Assert
    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        f"local-integration.sh: needs Python >= 3.10, and '{interpreter}' {says}; set PYTHON in .env.local"
    ]


@needs_bash
def test_a_line_that_is_no_setting_is_reported_by_its_number_alone(workspace):
    # Arrange: a pasted secret, no `=` in it.
    _write_config(workspace, _valid_config(), (TOKEN,))

    # Act
    result = _run(workspace, "--check")

    # Assert
    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        f"local-integration.sh: .env.local:{len(_valid_config()) + 1}: not a KEY=value line"
    ]
    assert TOKEN not in result.stdout + result.stderr


@needs_bash
@pytest.mark.parametrize(
    ("args", "message"),
    [(["--bogus"], "unknown argument '--bogus'"), (["--check", "--check"], "too many arguments")],
    ids=["unknown", "too-many"],
)
def test_an_unknown_argument_fails_with_one_line_of_usage(workspace, args, message):
    # Act
    result = _run(workspace, *args)

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [f"local-integration.sh: {message}; usage: ./local-integration.sh [--check]"]


@needs_bash
def test_help_prints_the_usage_and_reads_no_config(workspace):
    # Act: the workspace has no `.env.local`, so a help that read it would fail.
    result = _run(workspace, "--help")

    # Assert
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("usage: ./local-integration.sh [--check]\n")


# --- a whole run, in a copy whose venv is seeded -------------------------------------------------------------------

# Every interpreter the script starts, `PYTHON` and the venv's own: it appends its environment to a record, then runs
# this test's interpreter, which has the requirements installed. As the venv's, it skips pip: the seeded venv needs no
# install, and the static test above pins the one the script runs.
RECORDING_PYTHON = """env >> "{record}"
case "$1 $2" in "-m pip") exit 0 ;; esac
exec "{python}" "$@"
"""

# What a run reads beside the script: the generator as the action runs it, and the report's helper.
RUN_FILES = ("main.py", "requirements.txt", "tools/__init__.py", "tools/local_integration.py")
RUN_TREES = ("generator_markdown", "templates")

# Other components' output a run must leave alone, under the same output root.
SIBLINGS = ("output/collector-gh/doc-source/doc-source.json", "output/toolkit/normalize-docs/generator-ready.json")


@pytest.fixture(name="seeded")
def _seeded(workspace, tmp_path):
    """
    The workspace with what a run reads beside the script, a venv the script reuses - built by the configured
    interpreter, from the `requirements.txt` beside it - and other components' output beside the generator's.
    """
    for name in RUN_FILES:
        (workspace / name).parent.mkdir(exist_ok=True)
        shutil.copyfile(REPO_ROOT / name, workspace / name)
    for name in RUN_TREES:
        shutil.copytree(REPO_ROOT / name, workspace / name, ignore=shutil.ignore_patterns("__pycache__"))
    body = RECORDING_PYTHON.format(
        record=(tmp_path / "child-environment.txt").as_posix(), python=Path(sys.executable).as_posix()
    )
    _executable(workspace / ".venv-local-integration" / "bin" / "python", body)
    shutil.copyfile(REPO_ROOT / "requirements.txt", workspace / ".venv-local-integration" / "requirements.txt")
    python = _executable(tmp_path / "bin" / "python", body)
    _write_config(workspace, {**_valid_config(), "PYTHON": python})
    for sibling in SIBLINGS:
        (workspace / sibling).parent.mkdir(parents=True)
        (workspace / sibling).write_text("{}", encoding="utf-8")
    return workspace


def _run_env(**variables: str) -> dict:
    # A rebuilt venv would install from the network; with no index it fails at once instead.
    return {**os.environ, "PIP_NO_INDEX": "1", **variables}


def _native(path: Path) -> str:
    """A path as the script hands it to the venv's Python: `C:/...` on Windows, a POSIX path elsewhere."""
    return path.resolve().as_posix()


@needs_bash
def test_a_run_renders_checks_and_reports_the_three_documents_from_the_example(seeded):
    # Act
    result = _run(seeded, env=_run_env())

    # Assert: the venv was reused, and the header says what ran on what.
    assert result.returncode == 0, result.stderr
    assert " -m venv " not in result.stderr
    output = f"{_native(seeded / 'output')}/generator-markdown"
    samples = seeded / "output" / "samples"
    assert result.stdout.splitlines()[:8] == [
        "== local-integration.sh",
        "generator-markdown:       unknown (not a git checkout)",
        f"living-doc-utilities:     {version('living-doc-utilities')}",
        f"python:                   {platform.python_version()} (.venv-local-integration/bin/python)",
        f"technical-project input:  {_native(samples / 'generator-ready.json')}",
        f"ui-test-catalog input:    {_native(samples / 'ui-test-catalog.json')}",
        f"coverage-matrix input:    {_native(samples / 'coverage-matrix.json')}",
        f"output:                   {output}",
    ]
    # Assert: each document type ran through `main.py` with the three inputs the action passes, and no title.
    runs = [line for line in result.stderr.splitlines() if line.startswith("+ env ")]
    assert [sorted(set(re.findall(r"\bINPUT_[A-Z_]+(?==)", run))) for run in runs] == [
        ["INPUT_DOCUMENT_TYPE", "INPUT_OUTPUT_PATH", "INPUT_SOURCE_PATH"]
    ] * 3
    assert [re.search(r"INPUT_DOCUMENT_TYPE=(\S+)", run).group(1) for run in runs] == list(INPUTS)
    assert all(run.endswith(" -E main.py") for run in runs)
    # Assert: the generator found a `GITHUB_OUTPUT` to write, so its log does not say it has none.
    assert "GITHUB_OUTPUT`" not in result.stderr
    # Assert: each document and run report written, checked and reported.
    assert _files(seeded / "output" / "generator-markdown") == sorted(
        name for document_type in INPUTS for name in (f"{document_type}.md", f"{document_type}.run-report.json")
    )
    for document_type in INPUTS:
        assert f"{document_type}: {output}/{document_type}.md" in result.stdout
    assert result.stdout.count("  view: inner") == 3
    assert "    not_loaded: 3" in result.stdout
    assert (
        result.stdout.splitlines()[-1]
        == f"local-integration.sh: the three documents are written and valid under {output}"
    )
    # Assert: the samples and the other components' output are kept.
    assert [name for name in [*SAMPLE_FILES, *SIBLINGS] if not (seeded / name).is_file()] == []


@needs_bash
def test_an_input_of_another_contract_stops_the_run_with_the_generators_line(seeded, tmp_path, write_sample):
    # Arrange: a collector output where the technical project's input belongs, and a previous run's document.
    collector_output = write_sample(doc_source.CONTRACT_ID, "inputs/doc-source.json")
    config = (seeded / ".env.local").read_text(encoding="utf-8")
    (seeded / ".env.local").write_text(
        f"{config}TECHNICAL_PROJECT_INPUT={collector_output.as_posix()}\n", encoding="utf-8", newline="\n"
    )
    stale = seeded / "output" / "generator-markdown" / "coverage-matrix.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("# Coverage matrix\n", encoding="utf-8")

    # Act
    result = _run(seeded, env=_run_env())

    # Assert: the generator's own line in its log, which goes to stdout, naming the toolkit command that writes the
    # input; then the script's one stderr line naming the document type. Nothing after it ran.
    assert result.returncode == 1
    assert [line.split(" - ERROR - ", 1)[1] for line in result.stdout.splitlines() if " - ERROR - " in line] == [
        f"Input `source-path` is '{_native(collector_output)}', a `doc-source` collector output; document type "
        "`technical-project` reads a `generator-ready` file, which the `living-doc-toolkit` command `normalize-docs` "
        "writes."
    ]
    assert result.stderr.splitlines()[-1] == (
        "local-integration.sh: the generator failed on 'technical-project' (exit 1); its log is above"
    )
    assert "== ui-test-catalog" not in result.stdout
    # Assert: the generator's directory holds nothing - the previous run's document was cleared, and the failed run
    # wrote none - and nothing beside it was cleared.
    assert _files(seeded / "output" / "generator-markdown") == []
    assert [name for name in [*SAMPLE_FILES, *SIBLINGS] if not (seeded / name).is_file()] == []


@needs_bash
def test_a_document_that_fails_its_report_stops_the_run_with_one_line_naming_the_document_type(seeded):
    # Arrange: a report that fails, as it does on a missing document or a run report that disagrees with its input.
    (seeded / "tools" / "local_integration.py").write_text(
        'import sys\nprint("technical-project: the document is empty: stub", file=sys.stderr)\nsys.exit(1)\n',
        encoding="utf-8",
    )

    # Act
    result = _run(seeded, env=_run_env())

    # Assert: the report's line, then the script's; no later document type ran.
    assert result.returncode == 1
    assert result.stderr.splitlines()[-2:] == [
        "technical-project: the document is empty: stub",
        "local-integration.sh: the 'technical-project' document failed its check",
    ]
    assert "== ui-test-catalog" not in result.stdout


@needs_bash
def test_a_token_in_the_shell_or_the_config_reaches_no_output_no_child_and_no_file(seeded, tmp_path):
    # Arrange: the token everywhere an operator's may be - the shell, an inherited action input the generator would
    # write into a document, and `.env.local`.
    config = (seeded / ".env.local").read_text(encoding="utf-8")
    (seeded / ".env.local").write_text(f"{config}GITHUB_TOKEN={TOKEN}\n", encoding="utf-8", newline="\n")
    env = _run_env(GITHUB_TOKEN=TOKEN, GH_TOKEN=TOKEN, INPUT_GITHUB_TOKEN=TOKEN, INPUT_DOCUMENT_TITLE=TOKEN)

    # Act
    result = _run(seeded, env=env)

    # Assert: the run passed, and the `.env.local` line was reported by its number - neither its key nor its value.
    assert result.returncode == 0, result.stderr
    assert f".env.local:{len(_valid_config()) + 1}: ignored, not a setting of this script" in result.stderr
    assert TOKEN not in result.stdout + result.stderr
    # Assert: no document or run report holds it.
    written = [path for path in (seeded / "output" / "generator-markdown").rglob("*") if path.is_file()]
    assert len(written) == 6
    assert [path.name for path in written if TOKEN in path.read_text(encoding="utf-8")] == []
    # Assert: what the script starts inherits neither the token nor any action input from the shell.
    child_environment = (tmp_path / "child-environment.txt").read_text(encoding="utf-8", errors="replace")
    assert "PATH=" in child_environment
    assert TOKEN not in child_environment
    assert {line.split("=")[0] for line in child_environment.splitlines() if line.startswith("INPUT_")} == {
        "INPUT_DOCUMENT_TYPE",
        "INPUT_OUTPUT_PATH",
        "INPUT_SOURCE_PATH",
    }
