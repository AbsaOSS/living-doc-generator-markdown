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
import re

import pytest
from living_doc_utilities.contracts import generator_ready
from living_doc_utilities.contracts.common import AcceptanceCriterion
from living_doc_utilities.contracts.envelope import ContractWarning

from generator_markdown.renderer import escape
from tests.samples import VIEWS, heading_anchors, rendered, sample, tokens

CONTRACT = generator_ready.CONTRACT_ID
SOURCE_URL = "https://github.com/absaoss/payments-service/blob/4f2c1e9a7b3d5f6081a2c3d4e5f60718293a4b5c/features/checkout.feature"


def _entity(document, entity_id):
    return next(entity for entity in document.content.entities if entity.entity_id == entity_id)


def _block(markdown: str, entity_id: str) -> str:
    """One entity's part of the document: from its heading to the next entity's or section's."""
    start = markdown.index(f"\n### {entity_id}\n")
    following = re.search(r"\n#{2,3} ", markdown[start + 1 :])
    return markdown[start : start + 1 + following.start()] if following else markdown[start:]


@pytest.mark.parametrize("view", VIEWS)
def test_a_user_story_and_a_functionality_show_their_state_badge_in_both_views(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert "**Checkout with a saved payment method** `ACTIVE`\n" in markdown
    assert "**Checkout as a guest** `DEPRECATED`\n" in markdown
    assert "**Validate card number** `ACTIVE`\n" in markdown


def test_a_feature_shows_its_derived_state_and_its_stub_reason_in_the_inner_view():
    # Act
    markdown = rendered(sample(CONTRACT, "inner"))

    # Assert
    block = _block(markdown, "FEAT-001")
    assert "**Checkout page** `ACTIVE` `DERIVED`\n" in block
    assert "*Surface not yet instrumented: surface not yet instrumented: awaiting UI test coverage*\n" in block


def test_a_feature_shows_neither_its_state_nor_its_stub_reason_in_the_release_view():
    # Act
    markdown = rendered(sample(CONTRACT, "release"))

    # Assert
    block = _block(markdown, "FEAT-001")
    assert "**Checkout page**\n" in block
    assert "`ACTIVE`" not in block
    assert "`DERIVED`" not in block
    assert "instrumented" not in markdown


@pytest.mark.parametrize(("view", "badges"), [("inner", " `DEPRECATED` `DERIVED`"), ("release", " `DEPRECATED`")])
def test_a_deprecated_feature_shows_the_deprecated_badge_in_both_views(view, badges):
    # Arrange
    document = sample(CONTRACT, view)
    _entity(document, "FEAT-001").state = "deprecated"

    # Act
    markdown = rendered(document)

    # Assert
    assert f"**Checkout page**{badges}\n" in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_an_entitys_preconditions_and_not_in_scope_show_under_it_in_both_views(view):
    # Act
    block = _block(rendered(sample(CONTRACT, view)), "US-001")

    # Assert
    assert "**Preconditions**\n\n- The customer is signed in.\n" in block
    assert "**Not in scope**\n\n- Guest checkout.\n" in block


@pytest.mark.parametrize("view", VIEWS)
def test_a_criterions_preconditions_and_not_in_scope_show_under_it_as_also_in_both_views(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert "- **Also requires:**\n    - The cart has at least one item.\n" in markdown
    assert "- **Also not in scope:**\n    - International shipping.\n" in markdown


def test_a_deprecated_entity_shows_its_badge_date_and_reason_in_the_inner_view():
    # Act
    block = _block(rendered(sample(CONTRACT, "inner")), "US-002")

    # Assert
    assert "`DEPRECATED`" in block
    assert "- **Deprecated on:** 2026-06-01\n" in block
    assert "- **Deprecation reason:** Superseded by the unified checkout flow.\n" in block


def test_a_deprecated_entity_shows_only_its_badge_in_the_release_view():
    # Act
    block = _block(rendered(sample(CONTRACT, "release")), "US-002")

    # Assert
    assert "**Checkout as a guest** `DEPRECATED`\n" in block
    assert "Deprecated on" not in block
    assert "2026-06-01" not in block
    assert "Superseded by the unified checkout flow." not in block


@pytest.mark.parametrize("view", VIEWS)
def test_a_deprecated_criterion_shows_its_state_in_its_header_and_its_removal_in_both_views(view):
    # Act
    block = _block(rendered(sample(CONTRACT, view)), "US-002")

    # Assert: a criterion carries no deprecation date or reason.
    assert "#### AC:US-002-01 (v1.5.0 - deprecated - removal planned v2.1.0)\n" in block
    assert "\n- removal planned v2.1.0\n" in block


def test_planned_and_backlog_criteria_show_in_the_inner_view():
    # Act
    markdown = rendered(sample(CONTRACT, "inner"))

    # Assert
    assert (
        "#### AC:US-001-02 (v1.6.0 - planned)\n\nA customer can split payment across two saved cards.\n\n" in markdown
    )
    assert "\n- planned v1.6.0\n" in markdown
    assert "#### AC:US-001-03 (planned)\n\nA customer can pay with a digital wallet.\n\n- backlog\n" in markdown


def test_the_release_view_holds_no_planned_criterion_so_shows_no_planned_or_backlog_row():
    # Act
    markdown = rendered(sample(CONTRACT, "release"))

    # Assert
    assert "planned v1.6.0" not in markdown
    assert "backlog" not in markdown
    assert "US-001-02" not in markdown
    assert "US-001-03" not in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_every_criterion_header_is_its_canonical_header(view):
    # Arrange
    document = sample(CONTRACT, view)

    # Act
    markdown = rendered(document)

    # Assert
    headers = [line[len("#### ") :] for line in markdown.splitlines() if line.startswith("#### ")]
    criteria = [criterion for entity in document.content.entities for criterion in entity.acceptance_criteria]
    assert headers == [escape(criterion.canonical_header()) for criterion in criteria]


@pytest.mark.parametrize(
    ("version", "state", "header"),
    [("1.2.0", "active", "#### AC:US-001-01 (v1.2.0 - active)\n"), (None, "planned", "#### AC:US-001-01 (planned)\n")],
)
def test_a_criterion_header_is_rendered_in_its_canonical_form(version, state, header):
    # Arrange
    document = sample(CONTRACT)
    _entity(document, "US-001").acceptance_criteria = [
        AcceptanceCriterion(id="US-001-01", state=state, version=version, description="A customer can pay.")
    ]

    # Act
    markdown = rendered(document)

    # Assert
    assert header in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_aspects_rationales_and_placeholder_values_show_in_both_views(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert (
        "- **Aspect:** desktop, mobile\n- **Rationale:** Keeping checkout to one step reduces cart abandonment.\n"
        in (markdown)
    )
    assert "- **Rationale:** Prevents obviously invalid card numbers from reaching the payment gateway.\n" in (
        _block(markdown, "FUNC-001")
    )


@pytest.mark.parametrize("view", VIEWS)
def test_a_keyword_criterion_shows_its_keywords_name_with_its_values_not_as_aspect(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    criterion = markdown[markdown.index("#### AC:US-001-04 ") : markdown.index("#### AC:US-001-05 ")]
    assert "- **payment\\_field:** card-holder, expiry-date, last-four-digits\n" in criterion
    assert "Aspect" not in criterion


def test_area_and_iteration_path_show_as_small_text_under_the_entity_in_the_inner_view():
    # Act
    block = _block(rendered(sample(CONTRACT, "inner")), "US-002")

    # Assert
    assert "\n*Area: Payments\\\\Checkout · Iteration: Payments\\\\Sprint 12*\n" in block


def test_area_and_iteration_path_are_hidden_in_the_release_view():
    # Act
    markdown = rendered(sample(CONTRACT, "release"))

    # Assert
    assert "Payments\\\\Checkout" not in markdown
    assert "Sprint 12" not in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_a_relation_links_to_its_targets_place_in_the_document(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    feature = _block(markdown, "FEAT-001")
    assert "- **User stories:** [US-001](#us-001)\n" in feature
    assert "- **Functionalities:** [FUNC-001](#func-001)\n" in feature
    assert "- **Parent:** [FEAT-001](#feat-001)\n" in _block(markdown, "FUNC-001")


@pytest.mark.parametrize("view", VIEWS)
def test_a_relation_to_an_id_the_document_does_not_hold_shows_the_id_unlinked(view):
    # Arrange: the sample holds both relations' targets; this document does not.
    document = sample(CONTRACT, view)
    document.content.entities = [
        entity for entity in document.content.entities if entity.entity_id not in {"FEAT-002", "US-010"}
    ]

    # Act
    markdown = rendered(document)

    # Assert
    assert "- **Feature dependencies:** FEAT-002\n" in _block(markdown, "FEAT-001")
    assert "- **Superseded by:** US-010\n" in _block(markdown, "US-002")
    assert "(#feat-002)" not in markdown
    assert "(#us-010)" not in markdown


@pytest.mark.parametrize("entity_id", ["機能", "...", "US-Ü1"])
def test_an_id_whose_anchor_renderers_derive_differently_or_not_at_all_shows_unlinked(entity_id):
    # Arrange: the contract gives an entity id no pattern.
    document = sample(CONTRACT)
    _entity(document, "US-001").entity_id = entity_id
    _entity(document, "FEAT-001").user_stories = [entity_id]

    # Act
    markdown = rendered(document)

    # Assert
    assert f"    - {escape(entity_id)} Checkout with a saved payment method\n" in markdown
    assert f"- **User stories:** {escape(entity_id)}\n" in markdown


def test_an_id_with_a_run_of_spaces_links_to_the_anchor_of_its_printed_heading():
    # Arrange
    document = sample(CONTRACT)
    _entity(document, "US-001").entity_id = "US  001"
    _entity(document, "FEAT-001").user_stories = ["US  001"]

    # Act
    markdown = rendered(document)

    # Assert
    assert "\n### US 001\n" in markdown
    assert "- **User stories:** [US 001](#us-001)\n" in markdown
    assert "us-001" in heading_anchors(markdown)


def test_two_ids_sharing_an_anchor_both_show_unlinked():
    # Arrange: a renderer numbers the second heading's anchor.
    document = sample(CONTRACT)
    _entity(document, "US-002").entity_id = "us-001"
    _entity(document, "FEAT-001").user_stories = ["US-001", "us-001"]

    # Act
    markdown = rendered(document)

    # Assert
    assert "- **User stories:** US-001, us-001\n" in markdown
    assert "(#us-001)" not in markdown


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("business_value", "**Business value**\n\n"),
        ("preconditions", "**Preconditions**\n\n"),
        ("not_in_scope", "**Not in scope**\n\n"),
        ("notes", "**Notes**\n\n"),
    ],
)
def test_a_bullet_list_entry_holding_a_nested_line_renders_as_a_nested_list(field, label):
    # Arrange: as a parser keeps a nested item in its parent's string.
    document = sample(CONTRACT)
    setattr(
        _entity(document, "US-001"),
        field,
        ["Parent.\n  - Child.\n    - Grandchild,\n      wrapped.\n  - Second child.", "Sibling."],
    )

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        f"{label}- Parent.\n    - Child.\n        - Grandchild, wrapped.\n    - Second child.\n- Sibling.\n" in markdown
    )
    nested_items = [t for t in tokens(markdown) if t.type == "list_item_open" and t.level > 2]
    assert len(nested_items) >= 3
    assert all("- Child" not in t.content for t in tokens(markdown) if t.type == "inline")


def test_a_nested_item_after_a_tab_renders_as_a_nested_list():
    # Arrange: a parser keeps an authored `*<TAB>Child.` as `-<TAB>Child.`.
    document = sample(CONTRACT)
    _entity(document, "US-001").business_value = ["Parent.\n  -\tChild."]

    # Act
    markdown = rendered(document)

    # Assert
    assert "**Business value**\n\n- Parent.\n    - Child.\n" in markdown


@pytest.mark.parametrize(
    ("field", "label"), [("preconditions", "Also requires"), ("not_in_scope", "Also not in scope")]
)
def test_a_criterions_nested_item_renders_as_a_nested_list(field, label):
    # Arrange
    document = sample(CONTRACT)
    setattr(_entity(document, "US-001").acceptance_criteria[0], field, ["Parent.\n  - Child."])

    # Act
    markdown = rendered(document)

    # Assert
    assert f"- **{label}:**\n    - Parent.\n        - Child.\n" in markdown


def test_the_collector_warnings_naming_an_entity_show_under_it_with_a_link_to_their_line():
    # Act
    block = _block(rendered(sample(CONTRACT, "inner")), "US-001")

    # Assert: before the first criterion's heading, so no criterion seems to hold them.
    assert "**Not loaded from the input**\n\n" in block
    assert block.index("**Not loaded from the input**") < block.index("\n#### ")
    assert (
        "- `MALFORMED_AC` Acceptance criterion declares its variants more than once (Aspect, payment\\_field); "
        f"keep one 'Aspect:' or one keyword. (features/checkout.feature, [line 31]({SOURCE_URL}#L31))\n"
    ) in block
    assert (
        "- `UNPARSED_AC_LINE` Bullet 'device' is not a keyword: the description names no '\\{device\\}'. "
        f"(features/checkout.feature, [line 17]({SOURCE_URL}#L17))\n"
    ) in block


def test_a_collector_warning_naming_no_entity_shows_once_for_the_document_with_its_file_and_line():
    # Act
    markdown = rendered(sample(CONTRACT, "inner"))

    # Assert
    document_block = markdown[markdown.index("\n## Not loaded from the input\n") :]
    assert document_block == (
        "\n## Not loaded from the input\n\n"
        "- `MISSING_ENTITY_ID` Feature-header banner carries no 'LIVING DOC — ...' title line. "
        "(features/refund.feature, [line 1](https://github.com/absaoss/payments-service/blob/"
        "4f2c1e9a7b3d5f6081a2c3d4e5f60718293a4b5c/features/refund.feature#L1))\n"
    )
    assert markdown.count("MISSING_ENTITY_ID") == 1


def test_a_collector_warning_naming_an_entity_the_document_does_not_hold_shows_for_the_document():
    # Arrange
    document = sample(CONTRACT)
    document.warnings = [
        ContractWarning(code="MALFORMED_AC", message="Dropped.", entity_id="US-999", line_no=4, path="a.feature")
    ]

    # Act
    markdown = rendered(document)

    # Assert
    assert markdown.endswith("\n## Not loaded from the input\n\n- `MALFORMED_AC` Dropped. (a.feature, line 4)\n")


@pytest.mark.parametrize(
    ("warning", "line"),
    [
        (
            ContractWarning(
                code="UNPARSED_AC_LINE", message="Unread.", entity_id="US-001", line_no=9, path="a.feature"
            ),
            "- `UNPARSED_AC_LINE` Unread. (a.feature, line 9)\n",
        ),
        (
            ContractWarning(code="UNPARSED_AC_LINE", message="Unread.", entity_id="US-001", line_no=9),
            "- `UNPARSED_AC_LINE` Unread. (line 9)\n",
        ),
        (
            ContractWarning(
                code="UNPARSED_AC_LINE",
                message="Unread.",
                entity_id="US-001",
                path="a.feature",
                source_url="https://example.com/a.feature",
            ),
            "- `UNPARSED_AC_LINE` Unread. ([a.feature](https://example.com/a.feature))\n",
        ),
        (
            ContractWarning(
                code="UNPARSED_AC_LINE", message="Unread.", entity_id="US-001", source_url="https://example.com/a"
            ),
            "- `UNPARSED_AC_LINE` Unread. ([source](https://example.com/a))\n",
        ),
        (
            ContractWarning(code="UNPARSED_AC_LINE", message="Unread.", entity_id="US-001"),
            "- `UNPARSED_AC_LINE` Unread.\n",
        ),
    ],
)
def test_a_warning_links_its_line_only_through_its_own_source_url(warning, line):
    # Arrange: never through the entity's `source_ref.url`.
    document = sample(CONTRACT)
    document.warnings = [warning]

    # Act
    block = _block(rendered(document), "US-001")

    # Assert
    assert line in block
    assert "#L" not in block


def test_a_warnings_context_ac_id_and_entity_id_are_never_shown():
    # Act
    markdown = rendered(sample(CONTRACT, "inner"))

    # Assert
    document = sample(CONTRACT)
    for warning in document.warnings:
        assert escape(warning.context) not in markdown
    assert "US-001-06" not in markdown
    assert "header=" not in markdown
    assert "entity=" not in markdown


@pytest.mark.parametrize("entity_id", ["US-001", None, "US-999"])
@pytest.mark.parametrize(
    "code", ["STALE_AC_REF", "PLANNED_AC_HAS_TESTS", "MISSING_INPUT", "URL_FETCH_REFUSED", "NOT_A_CODE"]
)
def test_a_warning_no_collector_emits_is_not_shown(code, entity_id):
    # Arrange: under an entity, or in the document's own block.
    document = sample(CONTRACT)
    document.warnings = [ContractWarning(code=code, message="Not ours.", entity_id=entity_id, line_no=3)]

    # Act
    markdown = rendered(document)

    # Assert
    assert code not in markdown
    assert "Not loaded from the input" not in markdown


def test_the_release_view_shows_nothing_of_what_was_not_loaded():
    # Act
    markdown = rendered(sample(CONTRACT, "release"))

    # Assert
    assert "Not loaded from the input" not in markdown
    for warning in sample(CONTRACT).warnings:
        assert warning.code not in markdown
        assert escape(warning.message) not in markdown
    assert "#L" not in markdown


@pytest.mark.parametrize(
    ("title", "input_title", "heading"),
    [
        ("", "Payments service", "# Payments service\n"),
        ("Our docs", "Payments service", "# Our docs\n"),
        ("", "", "# Technical project\n"),
    ],
)
def test_the_title_is_the_document_title_input_then_the_inputs_own_then_the_default(title, input_title, heading):
    # Arrange
    document = sample(CONTRACT)
    document.document.title = input_title

    # Act
    markdown = rendered(document, title)

    # Assert
    assert markdown.startswith(heading)


@pytest.mark.parametrize("view", VIEWS)
def test_the_header_names_the_view_the_version_and_the_selection(view):
    # Arrange
    document = sample(CONTRACT, view)
    selection = document.document.selection_summary

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        f"*View: {view} · version 1.4.0 · {selection.included_entities} of {selection.total_entities} entities and "
        f"{selection.included_acceptance_criteria} of {selection.total_acceptance_criteria} acceptance criteria "
        "selected*\n"
    ) in markdown
