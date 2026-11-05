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

"""Every documentation example parses: `yaml` configures only declared inputs, `json` parses, `python` runs."""

import json
import re
from typing import Any

import pytest
import yaml

from tests.docs.pages import APPROVED_PAGES, CodeBlock, action_yml, code_blocks, headings, read_page

ACTION = "AbsaOSS/living-doc-generator-markdown"
# GitHub resolves `owner/repo` in `uses:` regardless of case.
_USES_RE = re.compile(rf"uses:\s*(?P<quote>['\"]?){re.escape(ACTION)}@(?P<ref>[^'\"\s]+)(?P=quote)", re.IGNORECASE)
_RELEASE_TAG_RE = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_LANGUAGE_ALIASES = {"yml": "yaml", "py": "python", "python3": "python"}


def example_language(info: str) -> str:
    """The language of a fenced block: the first word of its info string, lowercased, with its aliases folded."""
    words = info.split()
    language = words[0].lower() if words else ""
    return _LANGUAGE_ALIASES.get(language, language)


def _examples(language: str) -> list:
    return [
        pytest.param(block, id=f"{page}#{index}")
        for page in sorted(APPROVED_PAGES)
        for index, block in enumerate(code_blocks(read_page(page)))
        if example_language(block.info) == language
    ]


def action_with_blocks(node: Any) -> list[dict]:
    """Every `with:` mapping in a parsed example that configures this action: a step that `uses` it, or a bare
    `with:` block with no step around it. Another action's `with:` (e.g. `actions/checkout`) is not ours."""
    found: list[dict] = []
    if isinstance(node, list):
        for item in node:
            found.extend(action_with_blocks(item))
    elif isinstance(node, dict):
        uses = node.get("uses")
        if isinstance(node.get("with"), dict) and (uses is None or str(uses).lower().startswith(f"{ACTION.lower()}@")):
            found.append(node["with"])
        for key, value in node.items():
            if key != "with":
                found.extend(action_with_blocks(value))
    return found


def yaml_example_problems(block: CodeBlock) -> list[str]:
    """Why a `yaml` example is wrong: it does not parse, or it sets an input `action.yml` does not declare."""
    try:
        payload = yaml.safe_load(block.code)
    except yaml.YAMLError as e:
        return [f"does not parse: {e}"]
    declared = set(action_yml()["inputs"])
    return [
        f"`with:` sets `{key}`, which `action.yml` does not declare"
        for with_block in action_with_blocks(payload)
        for key in with_block
        if key not in declared
    ]


@pytest.mark.parametrize("block", _examples("yaml"))
def test_yaml_example_parses_and_sets_only_declared_inputs(block):
    """The block parses as YAML, and every `with:` key it gives this action is an `action.yml` input."""
    assert yaml_example_problems(block) == []


@pytest.mark.parametrize("block", _examples("json"))
def test_json_example_parses(block):
    """The block parses as JSON."""
    json.loads(block.code)


@pytest.mark.parametrize("block", _examples("python"))
def test_python_example_runs(block, tmp_path, monkeypatch):
    """The block runs in a fresh namespace, in a temporary working directory."""
    monkeypatch.chdir(tmp_path)
    exec(compile(block.code, "<doc example>", "exec"), {"__name__": "doc_example"})


def test_the_pages_carry_examples():
    """The example check has something to check: the pages hold several `yaml` examples that use this action."""
    configuring = [param for param in _examples("yaml") if action_with_blocks(yaml.safe_load(param.values[0].code))]
    assert len(configuring) >= 2


def _release_refs_are_valid(refs: set[str]) -> bool:
    if len(refs) != 1:
        return False
    ref = next(iter(refs))
    return _RELEASE_TAG_RE.fullmatch(ref) is not None


def test_every_example_names_one_release_of_this_action():
    """Every `uses:` of this action on every page names the same release, so a release bump changes them all."""
    refs = {ref_m.group("ref") for page in APPROVED_PAGES for ref_m in _USES_RE.finditer(read_page(page))}
    assert _release_refs_are_valid(refs), f"the pages name invalid releases: {sorted(refs)}"


def test_planted_placeholder_ref_is_rejected() -> None:
    """A placeholder such as `<ref>` names no release."""
    assert not _release_refs_are_valid({"<ref>"})


@pytest.mark.parametrize("ref", ["main", "v0.2", "v0.2.0-rc.1"])
def test_non_release_refs_are_rejected(ref: str) -> None:
    """Branches and references outside the stable release-tag format are not releases."""
    assert not _release_refs_are_valid({ref})


def test_semver_release_ref_is_accepted() -> None:
    """A stable release tag with major, minor, and patch components is accepted."""
    assert _release_refs_are_valid({"v0.1.0"})


def test_multiple_release_refs_are_rejected() -> None:
    """Every documentation example must continue to use the same release."""
    assert not _release_refs_are_valid({"v0.1.0", "v0.1.1"})


def test_planted_quoted_second_release_is_rejected() -> None:
    """The documentation check extracts quoted YAML `uses:` refs before rejecting a second release."""
    page = f'- uses: {ACTION}@v0.1.0\n- uses: "{ACTION}@v0.0.9"\n'
    assert yaml.safe_load(page) == [
        {"uses": f"{ACTION}@v0.1.0"},
        {"uses": f"{ACTION}@v0.0.9"},
    ]
    refs = {match.group("ref") for match in _USES_RE.finditer(page)}
    assert refs == {"v0.1.0", "v0.0.9"}
    assert not _release_refs_are_valid(refs)


def test_planted_undeclared_input_is_reported():
    """A step of this action that sets an input `action.yml` does not declare fails; another action's step does not."""
    code = (
        "- uses: actions/checkout@v4\n  with:\n    fetch-depth: 0\n"
        f"- uses: {ACTION}@v0.1.0\n  with:\n    document-type: technical-project\n    document-titel: x\n"
    )
    assert yaml_example_problems(CodeBlock("yaml", code, "")) == [
        "`with:` sets `document-titel`, which `action.yml` does not declare"
    ]


def test_planted_lowercase_owner_is_checked_and_its_release_read():
    """`absaoss/living-doc-generator-markdown` is the same action on GitHub, so its inputs and release are checked."""
    code = "- uses: absaoss/living-doc-generator-markdown@v0.0.9\n  with:\n    document-titel: x\n"
    assert yaml_example_problems(CodeBlock("yaml", code, "")) == [
        "`with:` sets `document-titel`, which `action.yml` does not declare"
    ]
    assert {ref_m.group("ref") for ref_m in _USES_RE.finditer(code)} == {"v0.0.9"}


@pytest.mark.parametrize(
    "info, language",
    [
        ("yaml", "yaml"),
        ("yml", "yaml"),
        ("YAML", "yaml"),
        ("yaml title=step.yml", "yaml"),
        ("JSON", "json"),
        ("py", "python"),
        ("python3", "python"),
        ("shell", "shell"),
        ("", ""),
    ],
)
def test_every_spelling_of_a_language_is_checked(info, language):
    """A `yml`, `YAML` or annotated block is a `yaml` example; `py` and `python3` are `python`."""
    assert example_language(info) == language


def test_a_fence_in_a_list_item_or_a_blockquote_is_an_example():
    """GitHub renders an indented fence under a list item, and a quoted one, as code, so both are checked."""
    page = (
        "1. Add the step:\n\n    ```yaml\n    - uses: AbsaOSS/living-doc-generator-markdown@v0.1.0\n      with:\n"
        "        document-titel: x\n    ```\n\n> ```yml\n> with:\n>   source_path: x.json\n> ```\n"
    )
    blocks = code_blocks(page)
    assert [block.info for block in blocks] == ["yaml", "yml"]
    assert [problem for block in blocks for problem in yaml_example_problems(block)] == [
        "`with:` sets `document-titel`, which `action.yml` does not declare",
        "`with:` sets `source_path`, which `action.yml` does not declare",
    ]


def test_a_fence_on_the_list_marker_line_is_an_example():
    """`1. ```yaml` opens a block inside the item, so its inputs are checked and the page after it is still read."""
    page = (
        "1. ```yaml\n   - uses: AbsaOSS/living-doc-generator-markdown@v0.1.0\n     with:\n"
        "       document-titel: x\n   ```\n\n## Next\n"
    )
    blocks = code_blocks(page)
    assert [block.info for block in blocks] == ["yaml"]
    assert yaml_example_problems(blocks[0]) == ["`with:` sets `document-titel`, which `action.yml` does not declare"]
    assert headings(page, 2) == ["Next"]


@pytest.mark.parametrize(
    "page",
    [
        "- ```markdown\n  > [!NOTE]\n  > Text.\n  ```\n\n## Errors\n",
        "```markdown\n> ```\n## Not a heading\n```\n\n## Errors\n",
    ],
    ids=["list-item-fence", "top-level-fence"],
)
def test_a_quote_marker_inside_a_fence_is_code(page):
    """A `>` deeper than the fence's own blockquote is code: it neither ends nor closes the block."""
    assert headings(page, 2) == ["Errors"]


def test_an_unclosed_fence_ends_with_its_container():
    """A quoted fence with no closing run ends where the blockquote ends, as on GitHub, so the page goes on."""
    page = "> ```yaml\n> with:\n>   command: c\n\n## Contents\n"
    assert headings(page, 2) == ["Contents"]
    assert [block.code for block in code_blocks(page)] == ["with:\n  command: c\n"]


def test_an_indented_run_inside_a_top_level_fence_does_not_close_it():
    """Four spaces before a run inside a top-level fence make it code, not a closing fence."""
    page = "```markdown\n    ```\n## Not a heading\n```\n\n## Next\n"
    assert headings(page, 2) == ["Next"]


def test_planted_bare_with_block_is_checked_too():
    """A bare `with:` snippet configures this action, so its keys are checked."""
    assert yaml_example_problems(CodeBlock("yaml", "with:\n  source_path: x.json\n", "")) == [
        "`with:` sets `source_path`, which `action.yml` does not declare"
    ]


def test_planted_unparseable_yaml_is_reported():
    """A block that is not YAML fails."""
    problems = yaml_example_problems(CodeBlock("yaml", "with:\n  document-type: [unclosed\n", ""))
    assert len(problems) == 1 and problems[0].startswith("does not parse:")


def test_a_commented_out_example_is_no_example():
    """A fence inside an HTML comment is not rendered, so it is neither parsed nor run."""
    assert code_blocks("<!--\n```python\nraise SystemExit('ran')\n```\n-->\n") == []


def test_a_comment_marker_inside_a_code_block_is_code():
    """`<!--` inside a real code block is code: the block is returned and the page after it is still read."""
    page = "```html\n<!--\n```\n\n## After\n"
    assert [block.code for block in code_blocks(page)] == ["<!--\n"]
    assert headings(page, 2) == ["After"]


def test_a_fence_indented_four_spaces_outside_a_list_is_indented_code():
    """Without a list item around it, a fence indented four spaces is indented code on GitHub: no example to run."""
    assert code_blocks("Intro.\n\n    ```python\n    raise SystemExit\n    ```\n") == []


def test_a_fence_indented_four_spaces_after_a_list_ended_is_indented_code():
    """A paragraph at the margin after a blank line ends the list, so a later four-space fence is indented code."""
    assert code_blocks("- item\n\nParagraph.\n\n    ```python\n    raise SystemExit\n    ```\n") == []


def test_a_fence_indented_four_spaces_inside_a_list_item_is_an_example():
    """Inside a list item, a fence indented to the item's content is a fenced block, so it is checked."""
    assert [block.info for block in code_blocks("- item\n\n    ```python\n    x = 1\n    ```\n")] == ["python"]


@pytest.mark.parametrize(
    "page",
    [
        "- item\n\n    ```yaml\n  with:\n      document-titel: x\n    ```\n",
        "> ```yaml\n>with:\n>  document-titel: x\n> ```\n",
    ],
    ids=["list-content-left-of-the-opener", "no-space-after-the-quote-marker"],
)
def test_a_code_line_stays_in_its_block_while_its_container_holds_it(page):
    """A line left of the opener, but still in the list item, is code, as is one with no space after its `>`, so the
    block's inputs are checked."""
    assert [problem for block in code_blocks(page) for problem in yaml_example_problems(block)] == [
        "`with:` sets `document-titel`, which `action.yml` does not declare"
    ]


def test_a_line_left_of_the_list_item_ends_a_fence_in_it():
    """A line left of the item's content leaves the item, which ends the block, however the opener is indented."""
    page = "- item\n\n    ```yaml\n  a: 1\ntext\n\n## Next\n"
    assert [block.code for block in code_blocks(page)] == ["a: 1\n"]
    assert headings(page, 2) == ["Next"]
