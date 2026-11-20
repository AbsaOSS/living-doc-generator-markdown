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
A technical project and a coverage matrix list the entities of each type in ascending id order, whatever order the
input holds them in: in the overview, the chapters and the run report's render manifest. A criterion keeps its
authored order, and the input is only read.
"""

import re

import pytest
from living_doc_utilities.contracts import coverage_matrix, generator_ready
from living_doc_utilities.contracts.coverage_matrix import AcCoverage

from generator_markdown.presentation import present, render_manifest
from tests.samples import VIEWS, rendered, sample

TECHNICAL_PROJECT = generator_ready.CONTRACT_ID
COVERAGE_MATRIX = coverage_matrix.CONTRACT_ID

# Each sample's entities in ascending id order within each type, the types in the canon's order.
ORDER = {
    TECHNICAL_PROJECT: [
        "US-001",
        "US-002",
        "US-010",
        "FEAT-001",
        "FEAT-002",
        "FEAT-003",
        "FUNC-001",
        "FUNC-002",
        "FUNC-003",
    ],
    COVERAGE_MATRIX: ["US-001", "US-002", "US-010", "FUNC-001", "FUNC-002", "FUNC-003"],
}


def _entities(document):
    return document.content.entities if document.schema_version == TECHNICAL_PROJECT else document.entities


def _criterion_ids(entity):
    return [
        criterion.ac_id if isinstance(criterion, AcCoverage) else criterion.id
        for criterion in entity.acceptance_criteria
    ]


def _shuffled(contract_id, view):
    """The sample with its entities out of order: every second one first, as a source's files may be read."""
    document = sample(contract_id, view)
    entities = _entities(document)
    entities[:] = entities[1::2] + entities[::2]
    assert [entity.entity_id for entity in entities] != ORDER[contract_id]
    return document


@pytest.mark.parametrize("view", VIEWS)
def test_a_shuffled_technical_project_lists_its_entities_in_id_order_in_the_overview_and_the_chapters(view):
    # Arrange
    document = _shuffled(TECHNICAL_PROJECT, view)

    # Act
    markdown = rendered(document)

    # Assert
    overview = markdown[markdown.index("## Overview\n") : markdown.index("\n## User Stories\n")]
    assert re.findall(r"^\| \[([^\]]+)\]", overview, re.MULTILINE) == ORDER[TECHNICAL_PROJECT]
    assert re.findall(r"^### (.+)$", markdown, re.MULTILINE) == ORDER[TECHNICAL_PROJECT]


@pytest.mark.parametrize("view", VIEWS)
def test_a_shuffled_coverage_matrix_lists_its_entities_in_id_order_in_the_chapters(view):
    # Arrange
    document = _shuffled(COVERAGE_MATRIX, view)

    # Act
    markdown = rendered(document)

    # Assert
    assert re.findall(r"^### (.+)$", markdown, re.MULTILINE) == ORDER[COVERAGE_MATRIX]


@pytest.mark.parametrize("contract_id", [TECHNICAL_PROJECT, COVERAGE_MATRIX])
def test_the_render_manifest_lists_the_entities_criteria_and_badges_in_the_documents_order(contract_id):
    # Arrange
    by_id = {entity.entity_id: entity for entity in _entities(sample(contract_id))}
    criteria = [criterion for entity_id in ORDER[contract_id] for criterion in _criterion_ids(by_id[entity_id])]

    # Act
    manifest = render_manifest(present(_shuffled(contract_id, "inner")))

    # Assert
    assert manifest["entities"] == ORDER[contract_id]
    assert manifest["acceptance_criteria"] == criteria
    badged = [item["id"] for item in manifest["badges"] if item["id"] in by_id]
    assert badged == ORDER[contract_id]


@pytest.mark.parametrize("contract_id", [TECHNICAL_PROJECT, COVERAGE_MATRIX])
def test_the_criteria_of_an_entity_keep_their_authored_order(contract_id):
    # Arrange: US-001's criteria, authored in reverse.
    document = _shuffled(contract_id, "inner")
    entity = next(entity for entity in _entities(document) if entity.entity_id == "US-001")
    entity.acceptance_criteria.reverse()
    authored = _criterion_ids(entity)

    # Act
    manifest = render_manifest(present(document))

    # Assert
    assert [ac_id for ac_id in manifest["acceptance_criteria"] if ac_id.startswith("US-001-")] == authored


@pytest.mark.parametrize("contract_id", [TECHNICAL_PROJECT, COVERAGE_MATRIX])
def test_the_input_keeps_its_own_order(contract_id):
    # Arrange
    document = _shuffled(contract_id, "inner")
    before = document.model_dump(mode="json")

    # Act
    present(document)

    # Assert
    assert document.model_dump(mode="json") == before


@pytest.mark.parametrize(
    ("ids", "order"),
    [
        (["US-10", "US-2", "US-1"], ["US-1", "US-2", "US-10"]),
        (["FEAT-2024-10", "FEAT-2024-3", "FEAT-2023-12"], ["FEAT-2023-12", "FEAT-2024-3", "FEAT-2024-10"]),
        (["機能", "US-3", "...", "US-1"], ["US-1", "US-3", "機能", "..."]),
        (["US-01", "US-1", "US-001"], ["US-01", "US-1", "US-001"]),
        (["US-٣", "US-10"], ["US-10", "US-٣"]),
        (["US-" + "9" * 5000, "US-10"], ["US-10", "US-" + "9" * 5000]),
    ],
    ids=[
        "numerically",
        "number by number",
        "an id without a number last",
        "equal numbers in input order",
        "ascii digits only",
        "a number of any length",
    ],
)
def test_the_entities_of_one_type_are_ordered_by_the_numbers_in_their_ids(ids, order):
    # Arrange: the contract gives an entity id no pattern.
    document = sample(TECHNICAL_PROJECT)
    story = next(entity for entity in document.content.entities if entity.entity_id == "US-001")
    document.content.entities = [story.model_copy(update={"entity_id": entity_id}) for entity_id in ids]

    # Act
    groups = present(document).groups

    # Assert
    assert [entity.id for entity in groups[0].entities] == order
