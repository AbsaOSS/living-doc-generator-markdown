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
The run report written beside each document: what the run read, counted from the input model, and the render manifest
of what the document shows.
"""

from collections import Counter
from typing import Any

from living_doc_utilities.contracts.compat import installed_utilities_version
from living_doc_utilities.contracts.coverage_matrix import CoverageMatrixResult
from living_doc_utilities.contracts.generator_ready import GeneratorReadyResult

from generator_markdown.action_inputs import DocumentType
from generator_markdown.presentation import Presentation, render_manifest
from generator_markdown.source_reader import SourceDocument

GENERATOR_NAME = "living-doc-generator-markdown"


def input_counts(document: SourceDocument) -> dict[str, Any]:
    """
    The input's records, counted from its model: `content.entities[]`, the matrix's rows, the catalog's groups.

    @param document: The input model.
    @return: The counts, under the names `metadata.stats.cardinality` gives them, which they equal.
    """
    entity_types: Counter[str] = Counter()
    criteria = 0
    scenarios = 0
    if isinstance(document, GeneratorReadyResult):
        entity_types.update(entity.type for entity in document.content.entities)
        criteria = sum(len(entity.acceptance_criteria) for entity in document.content.entities)
    elif isinstance(document, CoverageMatrixResult):
        entity_types.update(entity.type for entity in document.entities)
        criteria = sum(len(entity.acceptance_criteria) for entity in document.entities)
    else:
        # A scenario is counted in each group that lists it, as the catalog's cardinality counts it.
        for catalog in document.feature_files:
            groups = catalog.linked_to_user_story + catalog.linked_to_functionality
            scenarios += sum(len(group.scenarios) for group in groups) + len(catalog.unlinked)
    return {
        "entities": sum(entity_types.values()),
        "entities_by_type": dict(entity_types),
        "acceptance_criteria": criteria,
        "scenarios": scenarios,
        "warnings_by_code": dict(Counter(warning.code for warning in document.warnings)),
    }


def run_report(
    document_type: DocumentType, document: SourceDocument, presentation: Presentation, document_file: str
) -> dict[str, Any]:
    """
    The run report of one rendered document.

    @param document_type: The rendered document type.
    @param document: The input model.
    @param presentation: The model the document was rendered from.
    @param document_file: The document's file name in `output-path`.
    @return: Plain JSON-ready data.
    """
    producer = document.metadata.producer
    return {
        "generator": {"name": GENERATOR_NAME, "utilities_version": installed_utilities_version()},
        "document_type": document_type.value,
        "document": document_file,
        "title": presentation.title,
        "view": presentation.view,
        "input": {
            "schema_version": document.schema_version,
            "producer": {
                "name": producer.name,
                "version": producer.version,
                "utilities_version": producer.utilities_version,
            },
        },
        "counts": input_counts(document),
        "render_manifest": render_manifest(presentation),
    }
