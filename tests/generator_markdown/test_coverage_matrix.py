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
from living_doc_utilities.contracts import coverage_matrix
from living_doc_utilities.contracts.coverage_matrix import CoverageMatrixResult, CoverageSummary, EntityCoverage

from generator_markdown.presentation import present
from generator_markdown.renderer import escape
from tests.samples import VIEWS, heading_anchors, rendered, sample, tokens

CONTRACT = coverage_matrix.CONTRACT_ID
SUMMARY_HEADER = "| Coverage | Counted | Covered | Partially covered | Not covered |\n|---|---|---|---|---|\n"
OVERVIEW_HEADER = (
    "| ID | Title | State | Coverage | Counted | Covered | Partially covered | Not covered |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def _entity_block(markdown: str, entity_id: str) -> str:
    start = markdown.index(f"\n### {entity_id}\n")
    end = markdown.find("\n### ", start + 1)
    return markdown[start:] if end == -1 else markdown[start:end]


def _overview(markdown: str) -> str:
    return markdown[markdown.index("## Summary\n") : markdown.index("\n## User Stories\n")]


def _entity(document: CoverageMatrixResult, entity_id: str) -> EntityCoverage:
    return next(entity for entity in document.entities if entity.entity_id == entity_id)


@pytest.mark.parametrize(("view", "next_section"), [("inner", "## Planned work"), ("release", "## User Stories")])
def test_the_summary_opens_with_the_totals_then_one_table_per_entity_type_in_id_order(view, next_section):
    # Arrange: the input holds its entities in reverse id order.
    document = sample(CONTRACT, view)
    document.entities = list(reversed(document.entities))

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        f"## Summary\n\n{SUMMARY_HEADER}| 33.3% | 7 | 2 | 1 | 4 |\n\n"
        f"**User Stories**\n\n{OVERVIEW_HEADER}"
        "| [US-001](#us-001) | Checkout with a saved payment method | `ACTIVE` | 44.4% | 3 | 1 | 1 | 1 |\n"
        "| [US-002](#us-002) | Checkout as a guest | `DEPRECATED` | 100.0% | 1 | 1 | 0 | 0 |\n"
        "| [US-010](#us-010) | Unified checkout | `ACTIVE` | not applicable | 0 | 0 | 0 | 0 |\n\n"
        f"**Functionalities**\n\n{OVERVIEW_HEADER}"
        "| [FUNC-001](#func-001) | Validate card number | `ACTIVE` | not applicable | 0 | 0 | 0 | 0 |\n"
        "| [FUNC-002](#func-002) | Charge a saved card | `ACTIVE` | 0.0% | 3 | 0 | 0 | 3 |\n"
        "| [FUNC-003](#func-003) | Charge through the legacy gateway | `DEPRECATED` | not applicable | 0 | 0 | 0 | 0 |\n\n"
        f"{next_section}\n"
    ) in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_every_overview_link_goes_to_its_entitys_chapter(view):
    # Arrange
    markdown = rendered(sample(CONTRACT, view))
    flat = tokens(_overview(markdown))

    # Act
    links = [(flat[i + 1].content, token.attrGet("href")) for i, token in enumerate(flat) if token.type == "link_open"]

    # Assert: each link's target is the anchor a renderer derives from its entity's `###` heading.
    assert [text for text, _ in links] == ["US-001", "US-002", "US-010", "FUNC-001", "FUNC-002", "FUNC-003"]
    for text, href in links:
        assert f"\n### {text}\n" in markdown
        assert heading_anchors(f"### {text}\n") == {href[1:]}
        assert href[1:] in heading_anchors(markdown)


@pytest.mark.parametrize("entity_id", ["機能", "...", "US-Ü1"])
def test_an_id_whose_anchor_renderers_derive_differently_or_not_at_all_shows_unlinked_in_the_overview(entity_id):
    # Arrange: the contract gives an entity id no pattern.
    document = sample(CONTRACT)
    _entity(document, "US-001").entity_id = entity_id

    # Act
    markdown = rendered(document)

    # Assert
    assert f"| {escape(entity_id)} | Checkout with a saved payment method | `ACTIVE` | 44.4% |" in _overview(markdown)


def test_two_ids_sharing_an_anchor_both_show_unlinked_in_the_overview():
    # Arrange: a renderer numbers the second heading's anchor, so a link to the first would be the second's too.
    document = sample(CONTRACT)
    _entity(document, "US-002").entity_id = "us-001"

    # Act
    markdown = rendered(document)

    # Assert
    overview = _overview(markdown)
    assert "| US-001 | Checkout with a saved payment method |" in overview
    assert "| us-001 | Checkout as a guest |" in overview
    assert "(#us-001)" not in markdown


def test_a_hostile_entity_id_links_to_its_plain_anchor_with_its_text_escaped_in_the_overview():
    # Arrange
    document = sample(CONTRACT)
    _entity(document, "US-001").entity_id = "US-1 <script>x</script>](javascript:alert(1))"

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        "| [US-1 &lt;script&gt;x&lt;/script&gt;\\](javascript:alert(1))](#us-1-scriptxscriptjavascriptalert1) |"
    ) in _overview(markdown)
    assert "us-1-scriptxscriptjavascriptalert1" in heading_anchors(markdown)


def test_a_title_holding_table_syntax_stays_in_its_own_overview_cell():
    # Arrange
    document = sample(CONTRACT)
    _entity(document, "US-001").title = "Pay | INJECTED | cell |\n|---|---|\n| row"

    # Act
    flat = tokens(rendered(document))

    # Assert: the User Stories table's rows, after the totals' two, keep their eight cells; the title is one cell's text.
    widths: list[int] = []
    for token in flat:
        if token.type == "tr_open":
            widths.append(0)
        elif token.type in ("th_open", "td_open"):
            widths[-1] += 1
    assert widths[2:6] == [8, 8, 8, 8]
    assert "Pay | INJECTED | cell | |---|---| | row" in [t.content for t in flat if t.type == "text"]


def test_an_overview_row_shows_its_entitys_summary_as_written():
    # Arrange: `model_construct` skips the check that rejects such a summary in a file.
    valid = sample(CONTRACT)
    wrong = CoverageSummary.model_construct(
        counted_acs=7, covered_acs=6, partially_covered_acs=0, not_covered_acs=1, coverage_pct=12.5
    )
    first = valid.entities[0]
    entities = [EntityCoverage.model_construct(**{**dict(first), "summary": wrong}), *valid.entities[1:]]
    document = CoverageMatrixResult.model_construct(**{**dict(valid), "entities": entities})

    # Act
    markdown = rendered(document)

    # Assert
    assert (
        "| [US-001](#us-001) | Checkout with a saved payment method | `ACTIVE` | 12.5% | 7 | 6 | 0 | 1 |\n"
    ) in _overview(markdown)


def test_a_type_the_matrix_holds_no_entity_of_has_no_overview_table():
    # Arrange
    document = sample(CONTRACT)
    document.entities = [entity for entity in document.entities if entity.type == "DocumentedUserStory"]

    # Act
    markdown = rendered(document)

    # Assert
    assert "**User Stories**\n\n" in _overview(markdown)
    assert "Functionalities" not in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_a_partially_covered_row_shows_covered_over_declared_before_its_breakdown(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert: its scenarios are its aspects', in the breakdown.
    assert "| US-001-04 | active | `PARTIALLY COVERED` 1/3 | per aspect, below |\n" in markdown
    assert "| US-001-01 | active | `COVERED` | per aspect, below |\n" in markdown
    breakdown = markdown.index("**US-001-04** `PARTIALLY COVERED` 1/3\n\n| payment\\_field | Status | Scenarios |\n")
    assert breakdown > markdown.index("| US-001-04 | active |")


@pytest.mark.parametrize("view", VIEWS)
def test_a_breakdown_is_labelled_with_its_rows_keyword_or_aspect_when_it_has_none(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert (
        "**US-001-04** `PARTIALLY COVERED` 1/3\n\n"
        "| payment\\_field | Status | Scenarios |\n|---|---|---|\n"
        "| card-holder | covered | SCN-001 |\n| expiry-date | not covered | — |\n| last-four-digits | not covered | — |\n"
    ) in markdown
    assert "**US-001-01** `COVERED`\n\n| Aspect | Status | Scenarios |\n" in markdown
    assert "**US-001-05** `NOT COVERED`\n\n| Aspect | Status | Scenarios |\n" in markdown


@pytest.mark.parametrize("view", VIEWS)
def test_each_entitys_summary_and_the_matrixs_show_the_coverage_and_the_counts(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert f"## Summary\n\n{SUMMARY_HEADER}| 33.3% | 7 | 2 | 1 | 4 |\n" in markdown
    assert f"{SUMMARY_HEADER}| 44.4% | 3 | 1 | 1 | 1 |\n" in _entity_block(markdown, "US-001")
    assert f"{SUMMARY_HEADER}| 100.0% | 1 | 1 | 0 | 0 |\n" in _entity_block(markdown, "US-002")
    assert f"{SUMMARY_HEADER}| not applicable | 0 | 0 | 0 | 0 |\n\nNo counted criteria.\n" in (
        _entity_block(markdown, "FUNC-001")
    )


def test_the_planned_work_summary_shows_in_the_inner_view():
    # Act
    markdown = rendered(sample(CONTRACT, "inner"))

    # Assert
    assert (
        "## Planned work\n\nPlanned criteria are not counted.\n\n"
        "- **Planned:** 4\n- **Backlog:** 2\n- **v1.6.0:** 1\n- **v1.7.0:** 1\n"
    ) in markdown


def test_the_planned_work_summary_is_hidden_in_the_release_view():
    # Act
    markdown = rendered(sample(CONTRACT, "release"))

    # Assert
    assert "Planned" not in markdown
    assert "Backlog" not in markdown
    assert "v1.6.0" not in markdown


def test_nothing_is_recomputed_a_summary_disagreeing_with_its_rows_is_rendered_as_written():
    # Arrange: `model_construct` skips the check that rejects such a summary in a file.
    valid = sample(CONTRACT)
    wrong_entity = CoverageSummary.model_construct(
        counted_acs=7, covered_acs=6, partially_covered_acs=0, not_covered_acs=1, coverage_pct=12.5
    )
    wrong_matrix = CoverageSummary.model_construct(
        counted_acs=9, covered_acs=1, partially_covered_acs=2, not_covered_acs=6, coverage_pct=None
    )
    first = valid.entities[0]
    entities = [EntityCoverage.model_construct(**{**dict(first), "summary": wrong_entity}), *valid.entities[1:]]
    document = CoverageMatrixResult.model_construct(**{**dict(valid), "entities": entities, "summary": wrong_matrix})

    # Act
    presentation = present(document)
    markdown = rendered(document)

    # Assert
    assert presentation.summary.counted == 9
    assert f"## Summary\n\n{SUMMARY_HEADER}| not applicable | 9 | 1 | 2 | 6 |\n" in markdown
    assert f"{SUMMARY_HEADER}| 12.5% | 7 | 6 | 0 | 1 |\n" in _entity_block(markdown, "US-001")


@pytest.mark.parametrize("view", VIEWS)
def test_an_entity_shows_its_state_and_each_row_its_state_and_scenarios(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    block = _entity_block(markdown, "US-002")
    assert "**Checkout as a guest** `DEPRECATED`\n" in block
    assert "| US-002-01 | deprecated | `COVERED` | SCN-002 |\n" in block


@pytest.mark.parametrize(
    ("title", "heading"), [("", "# Coverage matrix\n"), ("Payments coverage", "# Payments coverage\n")]
)
def test_the_title_is_the_document_title_input_or_the_default(title, heading):
    # Act
    markdown = rendered(sample(CONTRACT), title)

    # Assert
    assert markdown.startswith(heading)
