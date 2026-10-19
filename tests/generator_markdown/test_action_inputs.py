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
import os

import pytest

from generator_markdown.action_inputs import (
    DEFAULT_OUTPUT_PATH,
    VALID_DOCUMENT_TYPES,
    ActionInputError,
    ActionInputs,
    DocumentType,
)


def test_valid_inputs_are_read_typed_and_the_output_path_resolved(valid_inputs, monkeypatch):
    # Arrange
    monkeypatch.setenv("INPUT_OUTPUT_PATH", "out/docs")
    monkeypatch.setenv("INPUT_DOCUMENT_TITLE", "  Payments  ")

    # Act
    inputs = ActionInputs.from_environment()

    # Assert: the output directory is absolute, resolved against the working directory.
    assert inputs == ActionInputs(
        document_type=DocumentType.TECHNICAL_PROJECT,
        source_path="generator-ready.json",
        output_path=os.fspath(valid_inputs / "out" / "docs"),
        document_title="Payments",
    )


@pytest.mark.parametrize("document_type", ["technical-project", "ui-test-catalog", "coverage-matrix"])
def test_every_document_type_is_accepted(valid_inputs, monkeypatch, document_type):
    # Arrange
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", document_type)

    # Act & Assert
    assert ActionInputs.from_environment().document_type.value == document_type


@pytest.mark.parametrize("output_path", [None, "", "   "])
def test_an_unset_or_empty_output_path_is_the_default_directory(valid_inputs, monkeypatch, output_path):
    # Arrange
    if output_path is not None:
        monkeypatch.setenv("INPUT_OUTPUT_PATH", output_path)

    # Act & Assert: the same default `action.yml` declares, resolved to an absolute path.
    assert ActionInputs.from_environment().output_path == os.path.abspath(DEFAULT_OUTPUT_PATH)
    assert DEFAULT_OUTPUT_PATH == "./output/generator-markdown"


def test_the_document_title_is_optional(valid_inputs):
    # Act & Assert
    assert ActionInputs.from_environment().document_title == ""


@pytest.mark.parametrize("document_type", [None, "", "  "])
def test_a_missing_document_type_names_the_input_and_lists_the_valid_types(monkeypatch, document_type):
    # Arrange: no input at all, an empty one and a blank one read the same.
    if document_type is not None:
        monkeypatch.setenv("INPUT_DOCUMENT_TYPE", document_type)

    # Act
    with pytest.raises(ActionInputError) as error:
        ActionInputs.from_environment()

    # Assert
    assert str(error.value) == (
        "Input `document-type` is required; valid types: technical-project, ui-test-catalog, coverage-matrix."
    )


@pytest.mark.parametrize("document_type", ["pdf", "Technical-Project", "technical-project\ncoverage-matrix"])
def test_an_unknown_document_type_names_the_input_its_value_and_the_valid_types(
    valid_inputs, monkeypatch, document_type
):
    # Arrange
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", document_type)

    # Act
    with pytest.raises(ActionInputError) as error:
        ActionInputs.from_environment()

    # Assert: one line, even for a value with a line break in it.
    message = str(error.value)
    assert (
        message == f"Input `document-type` is {document_type!r}, not a valid type; valid types: {VALID_DOCUMENT_TYPES}."
    )
    assert "\n" not in message


@pytest.mark.parametrize("source_path", [None, "", "  "])
def test_a_missing_source_path_names_the_input(valid_inputs, monkeypatch, source_path):
    # Arrange
    monkeypatch.delenv("INPUT_SOURCE_PATH")
    if source_path is not None:
        monkeypatch.setenv("INPUT_SOURCE_PATH", source_path)

    # Act
    with pytest.raises(ActionInputError) as error:
        ActionInputs.from_environment()

    # Assert
    assert str(error.value) == "Input `source-path` is required: the path to the input JSON file."
