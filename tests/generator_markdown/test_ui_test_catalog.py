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
The UI test catalog's layout (AbsaOSS/living-doc#155): the entities with their tested criteria, then the tests by
feature file. The inputs are built as `normalize-tests` groups a catalog: a scenario sits in the group of every entity
its links named before the release view's drop, and in `unlinked` when it named none.
"""

from typing import Any, Optional

import pytest
from living_doc_utilities.contracts import ui_test_catalog
from living_doc_utilities.contracts.ui_test_catalog import UiTestCatalogResult

from generator_markdown.presentation import present, render_manifest
from tests.samples import heading_anchors, heading_texts, rendered, sample, tokens

CONTRACT = ui_test_catalog.CONTRACT_ID
BLOB = "https://github.com/AbsaOSS/living-doc-testbed/blob/38904ce36d259de07414991564422c90cdc95c1a"
US_FILE = "projects/core/tests/e2e/features/liv_doc_us/us-001-borrow-a-book.feature"
FUNC_FILE = "projects/core/tests/e2e/features/liv_doc_func/func-010-total-fines-owed.feature"


def scenario(
    title: str,
    line: Optional[int],
    *links: tuple[str, Optional[str], Optional[str]],
    tags: tuple[str, ...] = (),
    steps: tuple[str, ...] = ("Given a step",),
    rule: Optional[str] = None,
    rule_background: tuple[str, ...] = (),
    dropped: tuple[str, ...] = (),
) -> dict[str, Any]:
    """A test with the links it holds, each `(criterion, state, aspect)`, and the criteria the release view dropped,
    which only place it in their entities' groups."""
    return {
        "title": title,
        "line": line,
        "tags": list(tags),
        "steps": list(steps),
        "rule": rule,
        "rule_background": list(rule_background),
        "acceptance_criteria": [{"id": ac_id, "state": state, "aspect": aspect} for ac_id, state, aspect in links],
        "placed": [ac_id for ac_id, _, _ in links] + list(dropped),
    }


def catalog(view: str, *files: tuple[str, list[str], list[dict[str, Any]]]) -> UiTestCatalogResult:
    """A catalog of `files`, each `(feature file, background, tests)`, grouped as `normalize-tests` groups it."""
    payload = sample(CONTRACT).model_dump(mode="json")
    payload["document"]["view"] = view
    payload["feature_files"] = []
    for feature_file, background, tests in files:
        entry: dict[str, Any] = {
            "feature_file": feature_file,
            "background": background,
            "linked_to_user_story": [],
            "linked_to_functionality": [],
            "unlinked": [],
        }
        groups: dict[str, dict[str, Any]] = {}
        for test in tests:
            placed = test.pop("placed")
            record = {
                **test,
                "scenario_id": f"absaoss/living-doc-testbed/{feature_file}::{test['title']}",
                "source_ref": {
                    "system": "GitHub",
                    "native_id": feature_file,
                    "native_type": "Scenario",
                    "url": f"{BLOB}/{feature_file}",
                    "tracker_state": "open",
                },
            }
            entity_ids = list(dict.fromkeys(ac_id.rsplit("-", 1)[0] for ac_id in placed))
            if not entity_ids:
                entry["unlinked"].append(record)
            for entity_id in entity_ids:
                if entity_id not in groups:
                    groups[entity_id] = {"entity_id": entity_id, "scenarios": []}
                    key = "linked_to_user_story" if entity_id.startswith("US-") else "linked_to_functionality"
                    entry[key].append(groups[entity_id])
                groups[entity_id]["scenarios"].append(record)
        payload["feature_files"].append(entry)
    return UiTestCatalogResult.model_validate(payload)


def agreed(view: str = "inner") -> UiTestCatalogResult:
    """Two of the testbed's `core` feature files, as AbsaOSS/living-doc#155 simulates them."""
    return catalog(
        view,
        (
            US_FILE,
            ["Given a member in good standing is signed in"],
            [
                scenario(
                    "Member borrows an available book",
                    56,
                    ("US-001-01", "active", None),
                    tags=("@Regression", "@AC:US-001-01"),
                    steps=(
                        'Given the book "The Hobbit" is available',
                        'When the member borrows "The Hobbit" from the catalogue',
                        'Then "The Hobbit" is listed on the My Loans page',
                        "And the loan shows a due date",
                    ),
                ),
                scenario(
                    "Member is offered a loan slip",
                    64,
                    ("US-001-04", "deprecated", None),
                    tags=("@AC:US-001-04",),
                    steps=(
                        'Given the book "Dune" is available',
                        'When the member borrows "Dune" from the catalogue',
                        'Then a printable loan slip for "Dune" is offered',
                    ),
                ),
            ],
        ),
        (
            FUNC_FILE,
            [],
            [
                scenario(
                    "Total fines add up across loans",
                    28,
                    ("FUNC-010-01", "active", None),
                    tags=("@AC:FUNC-010-01",),
                    steps=(
                        'Given the member owes 0.40 on "The Hobbit" and 1.20 on "Dune"',
                        "When the member opens the My Loans page",
                        "Then the total fines owed is 1.60",
                    ),
                ),
                scenario(
                    "Small fines add up to the cent",
                    36,
                    ("FUNC-010-01", "active", None),
                    tags=("@skip", "@AC:FUNC-010-01"),
                    steps=(
                        'Given the member owes 0.10 on "The Hobbit", 0.10 on "Dune" and 0.10 on "Emma"',
                        "When the member opens the My Loans page",
                        "Then the total fines owed is 0.30",
                    ),
                ),
                scenario(
                    "A settled fine is left out of the total",
                    43,
                    ("FUNC-010-02", "active", None),
                    tags=("@AC:FUNC-010-02",),
                    steps=(
                        'Given the member has a fine of 0.40 on "The Hobbit" and 1.20 on "Dune"',
                        'And the fine on "Dune" is <fine-state>',
                        "When the member opens the My Loans page",
                        "Then the total fines owed is 0.40",
                        "Examples:",
                        "  | fine-state  |",
                        "  | paid        |",
                        "  | waived      |",
                        "  | written-off |",
                    ),
                ),
            ],
        ),
    )


AGREED = f"""# UI test catalog

- [User Stories](#user-stories)
    - [US-001](#us-001)
- [Functionalities](#functionalities)
    - [FUNC-010](#func-010)
- [User Story tests](#user-story-tests)
    - [us-001-borrow-a-book.feature](#us-001-borrow-a-bookfeature)
- [Functionality tests](#functionality-tests)
    - [func-010-total-fines-owed.feature](#func-010-total-fines-owedfeature)

---

## User Stories

1 User Story: each tested criterion with its state and the tests that cover it.

---

### US-001

2 tests.

| AC | AC state | Test | Test state | Aspect | Tags |
|---|---|---|---|---|---|
| US-001-01 | `ACTIVE` | [Member borrows an available book](#test-member-borrows-an-available-book) | — | — | @Regression |
| US-001-04 | `DEPRECATED` | [Member is offered a loan slip](#test-member-is-offered-a-loan-slip) | — | — | — |

[Home](#ui-test-catalog)

---

## Functionalities

1 Functionality: each tested criterion with its state and the tests that cover it.

---

### FUNC-010

3 tests, 1 skipped.

| AC | AC state | Test | Test state | Aspect | Tags |
|---|---|---|---|---|---|
| FUNC-010-01 | `ACTIVE` | [Total fines add up across loans](#test-total-fines-add-up-across-loans) | — | — | — |
| FUNC-010-01 | `ACTIVE` | [Small fines add up to the cent](#test-small-fines-add-up-to-the-cent) | `SKIPPED` | — | @skip |
| FUNC-010-02 | `ACTIVE` | [A settled fine is left out of the total](#test-a-settled-fine-is-left-out-of-the-total) | — | — | — |

[Home](#ui-test-catalog)

---

## User Story tests

1 feature file, 2 tests, each with its metadata and steps.

- [us-001-borrow-a-book.feature](#us-001-borrow-a-bookfeature)

---

### us-001-borrow-a-book.feature

- **Entity:** [US-001](#us-001)
- **Source:** [us-001-borrow-a-book.feature]({BLOB}/{US_FILE})

**Background**

```gherkin
Given a member in good standing is signed in
```

#### Test: Member borrows an available book

- **Covers:** [US-001-01](#us-001)
- **Tags:** @Regression
- **Source:** [us-001-borrow-a-book.feature\\#L56]({BLOB}/{US_FILE}#L56)

```gherkin
Given the book "The Hobbit" is available
When the member borrows "The Hobbit" from the catalogue
Then "The Hobbit" is listed on the My Loans page
And the loan shows a due date
```

#### Test: Member is offered a loan slip

- **Covers:** [US-001-04](#us-001)
- **Source:** [us-001-borrow-a-book.feature\\#L64]({BLOB}/{US_FILE}#L64)

```gherkin
Given the book "Dune" is available
When the member borrows "Dune" from the catalogue
Then a printable loan slip for "Dune" is offered
```

[Home](#ui-test-catalog)

---

## Functionality tests

1 feature file, 3 tests, each with its metadata and steps.

- [func-010-total-fines-owed.feature](#func-010-total-fines-owedfeature)

---

### func-010-total-fines-owed.feature

- **Entity:** [FUNC-010](#func-010)
- **Source:** [func-010-total-fines-owed.feature]({BLOB}/{FUNC_FILE})

#### Test: Total fines add up across loans

- **Covers:** [FUNC-010-01](#func-010)
- **Source:** [func-010-total-fines-owed.feature\\#L28]({BLOB}/{FUNC_FILE}#L28)

```gherkin
Given the member owes 0.40 on "The Hobbit" and 1.20 on "Dune"
When the member opens the My Loans page
Then the total fines owed is 1.60
```

#### Test: Small fines add up to the cent

- **Status:** `SKIPPED`
- **Skipped, not counted:** [FUNC-010-01](#func-010)
- **Tags:** @skip
- **Source:** [func-010-total-fines-owed.feature\\#L36]({BLOB}/{FUNC_FILE}#L36)

```gherkin
Given the member owes 0.10 on "The Hobbit", 0.10 on "Dune" and 0.10 on "Emma"
When the member opens the My Loans page
Then the total fines owed is 0.30
```

#### Test: A settled fine is left out of the total

- **Covers:** [FUNC-010-02](#func-010)
- **Outline:** 3 examples
- **Source:** [func-010-total-fines-owed.feature\\#L43]({BLOB}/{FUNC_FILE}#L43)

```gherkin
Given the member has a fine of 0.40 on "The Hobbit" and 1.20 on "Dune"
And the fine on "Dune" is <fine-state>
When the member opens the My Loans page
Then the total fines owed is 0.40
Examples:
  | fine-state  |
  | paid        |
  | waived      |
  | written-off |
```

[Home](#ui-test-catalog)
"""


def _separator_problems(markdown: str) -> list[str]:
    """Each `---` that is not between two chapters: under a heading, next to another `---`, or at an end."""
    blocks = [block for block in markdown.split("\n\n") if block.strip()]
    problems = []
    for index, block in enumerate(blocks):
        if block != "---":
            continue
        before = blocks[index - 1] if index else None
        after = blocks[index + 1] if index + 1 < len(blocks) else None
        if before is None or after is None or before == "---" or after == "---" or before.startswith("#"):
            problems.append(f"--- after {before!r}, before {after!r}")
    return problems


def _internal_links(markdown: str) -> list[str]:
    return [
        token.attrGet("href")[1:]
        for token in tokens(markdown)
        if token.type == "link_open" and str(token.attrGet("href")).startswith("#")
    ]


def test_the_catalog_has_the_layout_agreed_on_living_doc_155():
    # Act
    markdown = rendered(agreed())

    # Assert
    assert markdown == AGREED


@pytest.mark.parametrize("document", [agreed(), sample(CONTRACT)], ids=["agreed", "full-sample"])
def test_a_separator_stands_only_between_chapters_and_no_document_names_its_view(document):
    # Act
    markdown = rendered(document)

    # Assert
    assert _separator_problems(markdown) == []
    assert "View:" not in markdown


@pytest.mark.parametrize("document", [agreed(), sample(CONTRACT)], ids=["agreed", "full-sample"])
def test_every_heading_is_unique_and_every_link_inside_the_document_finds_its_heading(document):
    # Act
    markdown = rendered(document)

    # Assert
    texts = heading_texts(markdown)
    assert len(heading_anchors(markdown)) == len(texts)
    assert set(_internal_links(markdown)) <= heading_anchors(markdown)


def test_a_title_that_repeats_among_the_tests_gets_its_files_name():
    # Arrange
    document = catalog(
        "inner",
        (
            "liv_doc_func/func-008-sort-results.feature",
            [],
            [scenario("Successful login", 9, ("FUNC-008-01", "active", None))],
        ),
        (
            "liv_doc_func/func-009-loan-list-states.feature",
            [],
            [
                scenario("Successful login", 7, ("FUNC-009-01", "active", None)),
                scenario("Failed login", 12, ("FUNC-009-02", "active", None)),
            ],
        ),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert [text for text in heading_texts(markdown) if text.startswith("Test: ")] == [
        "Test: Successful login (func-008-sort-results)",
        "Test: Successful login (func-009-loan-list-states)",
        "Test: Failed login",
    ]
    assert (
        "| FUNC-009-01 | `ACTIVE` | [Successful login (func-009-loan-list-states)]"
        "(#test-successful-login-func-009-loan-list-states) | — | — | — |"
    ) in markdown


def test_a_file_that_links_a_user_story_is_a_user_story_file_and_names_every_entity_it_links():
    # Arrange
    document = catalog(
        "inner",
        (
            "checkout.feature",
            [],
            [
                scenario("Pay by card", 4, ("FUNC-002-01", "active", None), ("US-001-01", "active", None)),
                scenario("Pay by cash", 9, ("FUNC-001-01", "active", None)),
            ],
        ),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert "## Functionality tests" not in markdown
    assert (
        "## User Story tests\n\n1 feature file, 2 tests, each with its metadata and steps.\n\n"
        "- [checkout.feature](#checkoutfeature)\n\n---\n\n### checkout.feature\n\n"
        "- **Entities:** [US-001](#us-001), [FUNC-001](#func-001), [FUNC-002](#func-002)\n"
    ) in markdown
    assert "- **Covers:** [FUNC-002-01](#func-002), [US-001-01](#us-001)\n" in markdown
    assert "| FUNC-002-01 | `ACTIVE` | [Pay by card](#test-pay-by-card) | — | — | — |" in markdown
    assert "| US-001-01 | `ACTIVE` | [Pay by card](#test-pay-by-card) | — | — | — |" in markdown


def test_an_entitys_rows_go_by_criterion_then_by_test_one_row_per_criterion_and_test():
    # Arrange
    document = catalog(
        "inner",
        (
            "us-002-join-the-library.feature",
            [],
            [
                scenario(
                    "Applicant joins the library",
                    38,
                    ("US-002-02", "active", None),
                    ("US-002-01", "active", None),
                    tags=("@Regression", "@AC:US-002-02", "@AC:US-002-01"),
                ),
                scenario("Adult applicant gets an adult card", 51, ("US-002-03", "active", "adult")),
                scenario(
                    "Junior applicant gets a junior card",
                    57,
                    ("US-002-03", "active", "junior"),
                    ("US-002-03", "active", "teen"),
                ),
            ],
        ),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        "### US-002\n\n3 tests.\n\n"
        "| AC | AC state | Test | Test state | Aspect | Tags |\n"
        "|---|---|---|---|---|---|\n"
        "| US-002-01 | `ACTIVE` | [Applicant joins the library](#test-applicant-joins-the-library) | — | — | @Regression |\n"
        "| US-002-02 | `ACTIVE` | [Applicant joins the library](#test-applicant-joins-the-library) | — | — | @Regression |\n"
        "| US-002-03 | `ACTIVE` | [Adult applicant gets an adult card](#test-adult-applicant-gets-an-adult-card) | — | adult "
        "| — |\n"
        "| US-002-03 | `ACTIVE` | [Junior applicant gets a junior card](#test-junior-applicant-gets-a-junior-card) | — "
        "| junior, teen | — |\n"
    ) in markdown
    assert "- **Covers:** [US-002-03](#us-002) (junior), [US-002-03](#us-002) (teen)\n" in markdown


def test_the_inner_view_marks_a_test_without_a_link_and_lists_the_files_without_one_last():
    # Arrange
    document = catalog(
        "inner",
        ("checkout.feature", [], [scenario("Pay", 4, ("US-001-01", "active", None)), scenario("Browse", 9)]),
        ("smoke.feature", [], [scenario("Opens", 3), scenario("Closes", 6, tags=("@skip",))]),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert "#### Test: Browse\n\n- **Status:** `NO AC`\n- **Source:** " in markdown
    assert "Test: Opens" not in markdown
    assert markdown.endswith(
        "---\n\n## Not linked to an entity\n\n1 feature file whose tests link no criterion.\n\n"
        "- smoke.feature: 2 tests\n\n[Home](#ui-test-catalog)\n"
    )
    assert "- [Functionality tests](#functionality-tests)" not in markdown
    assert "    - [checkout.feature](#checkoutfeature)\n- [Not linked to an entity](#not-linked-to-an-entity)\n\n" in (
        markdown
    )


def test_the_release_view_decides_from_the_links_the_drop_left():
    # Arrange: `FUNC-012-01` and `FUNC-013-01` are planned; the toolkit dropped their links and kept the groups.
    document = catalog(
        "release",
        (
            "func-011.feature",
            [],
            [
                scenario("Redirect", 4, ("FUNC-011-01", "active", None)),
                scenario("Remember", 9, dropped=("FUNC-012-01",)),
                scenario("Plain", 14),
            ],
        ),
        ("func-013.feature", [], [scenario("Planned only", 3, dropped=("FUNC-013-01",))]),
        ("smoke.feature", [], [scenario("Opens", 3)]),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert [text for text in heading_texts(markdown)] == [
        "UI test catalog",
        "Functionalities",
        "FUNC-011",
        "Functionality tests",
        "func-011.feature",
        "Test: Redirect",
        "Test: Remember",
        "Test: Plain",
    ]
    assert "#### Test: Remember\n\n- **Source:** " in markdown
    assert "NO AC" not in markdown
    assert "Not linked" not in markdown


@pytest.mark.parametrize(("state", "badge"), [("planned", "`PLANNED`"), ("in_review", "`IN REVIEW`"), (None, "—")])
def test_the_ac_state_is_the_criterions_badge_or_a_dash_for_a_criterion_no_document_holds(state, badge):
    # Arrange
    document = catalog("inner", ("checkout.feature", [], [scenario("Pay", 4, ("US-001-01", state, None))]))

    # Act
    markdown = rendered(document)

    # Assert
    assert f"| US-001-01 | {badge} | [Pay](#test-pay) | — | — | — |" in markdown


def test_a_rule_names_each_of_its_tests_and_its_background_shows_once_before_its_first_test():
    # Arrange
    rule = "A saved card pays in one step"
    document = catalog(
        "inner",
        (
            "checkout.feature",
            ["Given the basket holds a book"],
            [
                scenario(
                    "Pay by saved card",
                    14,
                    ("US-001-01", "active", None),
                    rule=rule,
                    rule_background=("Given the customer has a saved card",),
                ),
                scenario(
                    "Pay by new card",
                    20,
                    ("US-001-02", "active", None),
                    rule=rule,
                    rule_background=("Given the customer has a saved card",),
                ),
            ],
        ),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        "**Background**\n\n```gherkin\nGiven the basket holds a book\n```\n\n"
        f"**Rule background:** {rule}\n\n```gherkin\nGiven the customer has a saved card\n```\n\n"
        "#### Test: Pay by saved card\n\n"
        f"- **Rule:** {rule}\n- **Covers:** [US-001-01](#us-001)\n"
    ) in markdown
    assert markdown.count("Given the customer has a saved card") == 1
    assert f"#### Test: Pay by new card\n\n- **Rule:** {rule}\n" in markdown


@pytest.mark.parametrize(
    ("steps", "outline"),
    [
        (("Given <a>", "Examples:", "  | a |", "  | 1 |"), "1 example"),
        (
            (
                "Given <a>",
                "Then the order shows",
                "  | field | value |",
                "  | a     | b     |",
                "Examples: small",
                "  | a |",
                "  | 1 |",
                "  | 2 |",
                "@slow",
                "Scenarios: large",
                "  | a |",
                "  | 9 |",
            ),
            "3 examples",
        ),
    ],
)
def test_an_outline_counts_the_rows_of_its_examples_tables_and_not_a_steps_data_table(steps, outline):
    # Arrange
    document = catalog(
        "inner", ("checkout.feature", [], [scenario("Pay", 4, ("US-001-01", "active", None), steps=steps)])
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert f"- **Outline:** {outline}\n" in markdown


def test_a_scenario_without_examples_shows_no_outline():
    # Act
    markdown = rendered(agreed())

    # Assert
    assert markdown.count("**Outline:**") == 1


def test_the_tags_leave_out_the_ac_tags():
    # Arrange
    document = catalog(
        "inner",
        (
            "checkout.feature",
            [],
            [
                scenario(
                    "Pay", 4, ("US-001-01", "active", None), tags=("@AC:US-001-01", "@smoke", "@AC:US-001-02/aspect:x")
                )
            ],
        ),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert "- **Tags:** @smoke\n" in markdown
    assert "| US-001-01 | `ACTIVE` | [Pay](#test-pay) | — | — | @smoke |" in markdown


def test_a_test_without_a_line_links_its_file_and_one_without_steps_shows_no_block():
    # Arrange
    document = catalog(
        "inner", ("checkout.feature", [], [scenario("Pay", None, ("US-001-01", "active", None), steps=())])
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert markdown.endswith(
        f"#### Test: Pay\n\n- **Covers:** [US-001-01](#us-001)\n- **Source:** [checkout.feature]({BLOB}/checkout.feature)"
        "\n\n[Home](#ui-test-catalog)\n"
    )


def test_steps_holding_a_backtick_fence_stay_inside_their_block():
    # Arrange
    steps = ("Given the note", "  ```", "  ````text", "  ```", "Then it shows")
    document = catalog(
        "inner", ("checkout.feature", [], [scenario("Pay", 4, ("US-001-01", "active", None), steps=steps)])
    )

    # Act
    markdown = rendered(document)

    # Assert
    blocks = [token for token in tokens(markdown) if token.type == "fence"]
    assert [(block.info, block.content) for block in blocks] == [("gherkin", "\n".join(steps) + "\n")]


def test_two_feature_files_of_one_name_are_told_apart_by_their_paths():
    # Arrange
    document = catalog(
        "inner",
        ("web/login.feature", [], [scenario("Web login", 4, ("US-001-01", "active", None))]),
        ("mobile/login.feature", [], [scenario("Mobile login", 4, ("US-001-02", "active", None))]),
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert "### mobile/login.feature\n" in markdown
    assert "### web/login.feature\n" in markdown
    assert markdown.index("### mobile/login.feature") < markdown.index("### web/login.feature")


def test_a_scenario_tagged_skip_shows_skipped_with_its_criteria_as_not_counted():
    # Act
    markdown = rendered(agreed())

    # Assert
    assert (
        "#### Test: Small fines add up to the cent\n\n- **Status:** `SKIPPED`\n"
        "- **Skipped, not counted:** [FUNC-010-01](#func-010)\n- **Tags:** @skip\n"
    ) in markdown


@pytest.mark.parametrize("tag", ["@Skip", "@SKIP", "skip", "@skipped", "@skip-on-ci"])
def test_only_the_exact_skip_tag_marks_a_scenario_skipped(tag):
    # Arrange
    document = catalog(
        "inner", ("checkout.feature", [], [scenario("Pay", 4, ("US-001-01", "active", None), tags=(tag,))])
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert "SKIPPED" not in markdown
    assert f"#### Test: Pay\n\n- **Covers:** [US-001-01](#us-001)\n- **Tags:** {tag}\n" in markdown
    assert "1 test.\n" in markdown


def test_a_skipped_scenario_shows_the_same_in_both_views():
    # Act
    inner = rendered(agreed("inner"))
    release_markdown = rendered(agreed("release"))

    # Assert
    assert release_markdown == inner


def test_the_manifest_names_the_entities_criteria_badges_and_tests_the_document_shows():
    # Act
    manifest = render_manifest(present(agreed()))

    # Assert
    assert manifest == {
        "view": "inner",
        "entities": ["US-001", "FUNC-010"],
        "acceptance_criteria": ["US-001-01", "US-001-04", "FUNC-010-01", "FUNC-010-02"],
        "aspects": [],
        "badges": [
            {"id": "US-001-01", "badges": ["ACTIVE"]},
            {"id": "US-001-04", "badges": ["DEPRECATED"]},
            {"id": "FUNC-010-01", "badges": ["ACTIVE"]},
            {"id": "FUNC-010-02", "badges": ["ACTIVE"]},
            {"id": "Small fines add up to the cent", "badges": ["SKIPPED"]},
        ],
        "scenarios": [
            "Member borrows an available book",
            "Member is offered a loan slip",
            "Total fines add up across loans",
            "Small fines add up to the cent",
            "A settled fine is left out of the total",
        ],
        "not_loaded": [],
    }


@pytest.mark.parametrize(
    ("title", "start", "home"),
    [
        ("", "# UI test catalog\n", "[Home](#ui-test-catalog)"),
        ("Checkout tests", "# Checkout tests\n", "[Home](#checkout-tests)"),
    ],
)
def test_the_title_is_the_document_title_input_or_the_default_and_home_links_to_it(title, start, home):
    # Act
    markdown = rendered(agreed(), title)

    # Assert
    assert markdown.startswith(start)
    assert markdown.count(home) == 4


def test_a_title_without_an_anchor_of_its_own_leaves_out_the_home_links():
    # Act
    markdown = rendered(agreed(), "Testy uživatelského rozhraní")

    # Assert
    assert "Home" not in markdown
    assert _separator_problems(markdown) == []
