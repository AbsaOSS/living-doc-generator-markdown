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
The action's input layer: it reads every `INPUT_*` variable `action.yml` passes and validates it, so the rest of the
generator receives typed, checked values and never reads the environment itself.
"""

import os
from dataclasses import dataclass
from enum import Enum

from living_doc_utilities.github.utils import get_action_input

# Input names as `action.yml` declares them; `get_action_input` maps each to its `INPUT_<NAME>` variable.
DOCUMENT_TYPE = "document-type"
SOURCE_PATH = "source-path"
OUTPUT_PATH = "output-path"
DOCUMENT_TITLE = "document-title"

# The same default `action.yml` gives `output-path`, for a run that passes the input empty.
DEFAULT_OUTPUT_PATH = "./output/generator-markdown"


class DocumentType(str, Enum):
    """The documents the generator renders, named as the `document-type` input takes them."""

    TECHNICAL_PROJECT = "technical-project"
    UI_TEST_CATALOG = "ui-test-catalog"
    COVERAGE_MATRIX = "coverage-matrix"


VALID_DOCUMENT_TYPES = ", ".join(document_type.value for document_type in DocumentType)


class ActionInputError(Exception):
    """A missing or invalid input; the message is the one line the run fails with, naming the input."""


@dataclass(frozen=True)
class ActionInputs:
    """The validated action inputs; `output_path` is resolved to an absolute path."""

    document_type: DocumentType
    source_path: str
    output_path: str
    document_title: str

    @classmethod
    def from_environment(cls) -> "ActionInputs":
        """
        Read and validate the action inputs, stopping at the first invalid one, in `action.yml` order.

        @return: The validated inputs.
        @raise ActionInputError: `document-type` or `source-path` is missing, or `document-type` is unknown.
        """
        raw_document_type = get_action_input(DOCUMENT_TYPE).strip()
        if not raw_document_type:
            raise ActionInputError(f"Input `{DOCUMENT_TYPE}` is required; valid types: {VALID_DOCUMENT_TYPES}.")
        try:
            document_type = DocumentType(raw_document_type)
        except ValueError as error:
            # `!r` keeps a value with a line break on the one line the run fails with.
            raise ActionInputError(
                f"Input `{DOCUMENT_TYPE}` is {raw_document_type!r}, not a valid type; "
                f"valid types: {VALID_DOCUMENT_TYPES}."
            ) from error

        source_path = get_action_input(SOURCE_PATH).strip()
        if not source_path:
            raise ActionInputError(f"Input `{SOURCE_PATH}` is required: the path to the input JSON file.")

        output_path = get_action_input(OUTPUT_PATH).strip() or DEFAULT_OUTPUT_PATH
        return cls(
            document_type=document_type,
            source_path=source_path,
            output_path=os.path.abspath(output_path),
            document_title=get_action_input(DOCUMENT_TITLE).strip(),
        )
