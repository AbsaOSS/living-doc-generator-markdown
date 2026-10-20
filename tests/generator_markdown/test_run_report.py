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
import json

import pytest
from living_doc_utilities.contracts.compat import installed_utilities_version

from generator_markdown.action_inputs import DocumentType
from generator_markdown.output_writer import OutputError, write_output
from generator_markdown.presentation import present, render_manifest
from generator_markdown.run_report import input_counts, run_report
from generator_markdown.source_reader import read_source
from tests.samples import CONTRACTS, DOCUMENT_TYPES, VIEWS, plain_text, rendered, sample

COUNTED = ["entities", "entities_by_type", "acceptance_criteria", "scenarios", "warnings_by_code"]


@pytest.mark.parametrize("contract_id", CONTRACTS)
def test_the_counts_come_from_the_input_model_and_equal_its_cardinality(write_sample, contract_id):
    # Arrange: `write_artifact` computes the file's `metadata.stats` from its content.
    document_type = DocumentType(DOCUMENT_TYPES[contract_id])
    document = read_source(document_type, str(write_sample(contract_id, "input.json")))

    # Act
    counts = input_counts(document)

    # Assert
    cardinality = document.metadata.stats.cardinality.model_dump()
    assert counts == {name: cardinality[name] for name in COUNTED}
    assert any(counts[name] for name in ("entities", "scenarios"))


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("contract_id", CONTRACTS)
def test_the_run_report_carries_the_input_the_counts_and_the_render_manifest(contract_id, view):
    # Arrange
    document_type = DocumentType(DOCUMENT_TYPES[contract_id])
    document = sample(contract_id, view)
    presentation = present(document, "A title")

    # Act
    report = run_report(document_type, document, presentation, f"{document_type.value}.md")

    # Assert
    assert report == {
        "generator": {"name": "living-doc-generator-markdown", "utilities_version": installed_utilities_version()},
        "document_type": document_type.value,
        "document": f"{document_type.value}.md",
        "title": "A title",
        "view": view,
        "input": {
            "schema_version": contract_id,
            "producer": {"name": "AbsaOSS/living-doc-toolkit", "version": "0.2.0", "utilities_version": "0.5.1"},
        },
        "counts": input_counts(document),
        "render_manifest": render_manifest(presentation),
    }
    assert report["render_manifest"]["view"] == view


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("contract_id", CONTRACTS)
def test_everything_the_render_manifest_names_is_in_the_rendered_document(contract_id, view):
    # Arrange
    document = sample(contract_id, view)

    # Act
    manifest = render_manifest(present(document))
    text = plain_text(rendered(document))

    # Assert
    named = manifest["entities"] + manifest["acceptance_criteria"] + manifest["scenarios"]
    named += [value for aspect in manifest["aspects"] for value in [aspect["label"] or "", *aspect["values"]]]
    named += [badge for entry in manifest["badges"] for badge in entry["badges"]]
    named += [item["code"] for item in manifest["not_loaded"]]
    assert [name for name in named if name not in text] == []


def test_the_technical_project_manifest_records_each_view():
    # Act
    inner = render_manifest(present(sample("generator-ready-v1.0.0", "inner")))
    release = render_manifest(present(sample("generator-ready-v1.0.0", "release")))

    # Assert
    assert inner["acceptance_criteria"] == [
        "US-001-01",
        "US-001-02",
        "US-001-03",
        "US-001-04",
        "US-001-05",
        "US-002-01",
    ]
    assert release["acceptance_criteria"] == ["US-001-01", "US-001-04", "US-001-05", "US-002-01"]
    assert {
        "ac_id": "US-001-04",
        "label": "payment_field",
        "values": ["card-holder", "expiry-date", "last-four-digits"],
    } in (inner["aspects"])
    assert {"id": "FEAT-001", "badges": ["ACTIVE", "DERIVED"]} in inner["badges"]
    assert "FEAT-001" not in [entry["id"] for entry in release["badges"]]
    assert inner["not_loaded"] == [
        {"code": "MALFORMED_AC", "under": "US-001"},
        {"code": "UNPARSED_AC_LINE", "under": "US-001"},
        {"code": "MISSING_ENTITY_ID", "under": None},
    ]
    assert release["not_loaded"] == []


def test_the_document_and_its_run_report_are_written_into_the_output_directory(tmp_path):
    # Act
    written = write_output(str(tmp_path / "out" / "docs"), DocumentType.COVERAGE_MATRIX, "# Doc\n", {"view": "inner"})

    # Assert
    assert written == [
        tmp_path / "out" / "docs" / "coverage-matrix.md",
        tmp_path / "out" / "docs" / "coverage-matrix.run-report.json",
    ]
    assert written[0].read_bytes() == b"# Doc\n"
    assert json.loads(written[1].read_text(encoding="utf-8")) == {"view": "inner"}
    assert written[1].read_bytes().endswith(b"}\n")


def test_an_output_path_that_cannot_be_a_directory_fails_with_one_line_naming_the_input(tmp_path):
    # Arrange
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    # Act
    with pytest.raises(OutputError) as error:
        write_output(str(blocker / "docs"), DocumentType.TECHNICAL_PROJECT, "# Doc\n", {})

    # Assert
    message = str(error.value)
    assert message.startswith(f"Input `output-path` is {str(blocker / 'docs')!r}, which cannot be written: ")
    assert "\n" not in message
