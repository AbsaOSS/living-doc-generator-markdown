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

"""`test.yml` runs these checks whenever a file they read changes: a page, `action.yml`, or a file a page anchors."""

import re
import shutil
import subprocess
from functools import lru_cache

import pytest
import yaml

from tests.docs.pages import ANCHOR_RE, APPROVED_PAGES, CODE_MAPS, REPO_ROOT, read_page

TEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"


@lru_cache(maxsize=1)
def changes_script() -> str:
    """The shell script of the `detect` job's `changes` step."""
    workflow = yaml.safe_load(TEST_WORKFLOW.read_text(encoding="utf-8"))
    return next(step["run"] for step in workflow["jobs"]["detect"]["steps"] if step.get("id") == "changes")


def change_filters() -> tuple[re.Pattern[str], ...]:
    """The `grep -E` patterns of the `changes` step, `python_changed` first, then `docs_changed`."""
    return tuple(re.compile(pattern) for pattern in re.findall(r"grep -E '([^']+)'", changes_script()))


def runs_tests(path: str, filters: tuple[re.Pattern[str], ...]) -> bool:
    """Whether a pull request that changes only `path` runs the `tests` job."""
    return any(change_filter.search(path) for change_filter in filters)


def unfiltered_anchor_paths(pages: dict[str, str], filters: tuple[re.Pattern[str], ...]) -> list[str]:
    """Each file a page anchors that a change of its own would not run the tests for."""
    paths = {anchor_m.group("path") for text in pages.values() for anchor_m in ANCHOR_RE.finditer(text)}
    return sorted(path for path in paths if not runs_tests(path, filters))


def test_the_detect_step_has_both_filters():
    """The `changes` step greps the changed files twice: `python_changed`, then `docs_changed`."""
    assert len(change_filters()) == 2


@pytest.mark.parametrize("path", [*sorted(APPROVED_PAGES), "action.yml", "local-integration.sh", ".env.local.example"])
def test_a_change_of_a_page_action_yml_or_the_local_run_runs_the_tests(path):
    """Every approved page, `action.yml`, the local integration script and its example configuration set a filter."""
    assert runs_tests(path, change_filters())


def test_the_docs_filter_matches_the_local_run_files_under_grep():
    """The `docs_changed` pattern, run by `grep -E` as the step runs it, prints both lines of
    `printf 'local-integration.sh\\n.env.local.example\\n'`."""
    grep = shutil.which("grep")
    if grep is None:
        pytest.skip("no grep on PATH")
    docs_filter = re.findall(r"grep -E '([^']+)'", changes_script())[1]
    found = subprocess.run(
        [grep, "-E", docs_filter],
        input="local-integration.sh\n.env.local.example\n",
        capture_output=True,
        check=False,
        text=True,
    )
    assert found.stdout.splitlines() == ["local-integration.sh", ".env.local.example"]


@pytest.mark.parametrize(
    "path",
    [
        "CHANGELOG.md",
        "NOTES.MD",
        "docs/x.markdown",
        "generator_markdown/README.md",
        "docs/topic/page.md",
        ".github/CONTRIBUTING.md",
    ],
)
def test_a_new_or_renamed_page_anywhere_runs_the_tests(path):
    """A page the list does not approve yet - `.md` or `.markdown`, in any case, as `tracked_markdown` lists them -
    or a page renamed out of it, still runs the page-list check."""
    assert runs_tests(path, change_filters())


def test_a_rename_lists_its_old_path_too():
    """A rename names the old path as well as the new one, on a pull request and on a push, so moving a file a page
    anchors (e.g. `dependabot.yml` to `.yaml`) still runs the tests."""
    script = changes_script()
    assert ".previous_filename // empty" in script
    assert "git diff --name-only --no-renames" in script


def test_a_change_of_a_file_a_page_anchors_runs_the_tests():
    """A workflow, script or config file a page or a code map anchors sets a filter, so renaming the anchored text
    fails at once."""
    anchoring = {*APPROVED_PAGES, *CODE_MAPS.values()}
    assert unfiltered_anchor_paths({path: read_page(path) for path in anchoring}, change_filters()) == []


def test_planted_anchor_into_an_unfiltered_file_is_reported():
    """An anchor into a file neither filter matches is reported."""
    pages = {"docs/x.md": "- a fact → `setup.cfg::flake8`\n- b → `main.py::run`\n"}
    assert unfiltered_anchor_paths(pages, change_filters()) == ["setup.cfg"]
