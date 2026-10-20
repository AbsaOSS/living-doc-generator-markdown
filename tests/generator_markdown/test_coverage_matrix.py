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
from tests.samples import VIEWS, rendered, sample

CONTRACT = coverage_matrix.CONTRACT_ID
SUMMARY_HEADER = "| Coverage | Counted | Covered | Partially covered | Not covered |\n|---|---|---|---|---|\n"


def _entity_block(markdown: str, entity_id: str) -> str:
    start = markdown.index(f"\n### {entity_id}\n")
    end = markdown.find("\n### ", start + 1)
    return markdown[start:] if end == -1 else markdown[start:end]


@pytest.mark.parametrize("view", VIEWS)
def test_a_partially_covered_row_shows_covered_over_declared_before_its_breakdown(view):
    # Act
    markdown = rendered(sample(CONTRACT, view))

    # Assert
    assert "| US-001-04 | active | `PARTIALLY COVERED` 1/3 | — |\n" in markdown
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
    assert f"## Summary\n\n{SUMMARY_HEADER}| 58.3% | 4 | 2 | 1 | 1 |\n" in markdown
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
        "- **Planned:** 2\n- **Backlog:** 1\n- **v1.6.0:** 1\n"
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
