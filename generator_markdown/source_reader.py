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
The generator's input reader: it reads `source-path` through `living-doc-utilities`' `read_artifact` as the one
contract its document type renders, and turns every way that read fails into one line naming the input.
"""

import json
import os
import re
from pathlib import Path
from typing import Union, cast

from living_doc_utilities.contracts.codes import Code, ContractError
from living_doc_utilities.contracts.compat import installed_utilities_version
from living_doc_utilities.contracts.coverage_matrix import CoverageMatrixResult
from living_doc_utilities.contracts.generator_ready import GeneratorReadyResult
from living_doc_utilities.contracts.io import read_artifact
from living_doc_utilities.contracts.ui_test_catalog import UiTestCatalogResult

from generator_markdown.action_inputs import SOURCE_PATH, DocumentType

SourceDocument = Union[GeneratorReadyResult, UiTestCatalogResult, CoverageMatrixResult]

# The one `living-doc-toolkit` output each document type renders, by contract name.
CONTRACT_NAMES: dict[DocumentType, str] = {
    DocumentType.TECHNICAL_PROJECT: "generator-ready",
    DocumentType.UI_TEST_CATALOG: "ui-test-catalog",
    DocumentType.COVERAGE_MATRIX: "coverage-matrix",
}

# The `living-doc-toolkit` command that writes each document type's input.
TOOLKIT_COMMANDS: dict[DocumentType, str] = {
    DocumentType.TECHNICAL_PROJECT: "normalize-docs",
    DocumentType.UI_TEST_CATALOG: "normalize-tests",
    DocumentType.COVERAGE_MATRIX: "coverage-matrix",
}

# The collector outputs: `living-doc-toolkit` reads them, a generator never does.
COLLECTOR_CONTRACT_NAMES = frozenset({"doc-source", "doc-entities", "ui-tests"})

_DOCUMENT_TYPES_BY_CONTRACT = {name: document_type for document_type, name in CONTRACT_NAMES.items()}

# `CONTRACT_MISMATCH` names the file's own contract only in its message: "expected one of [...], got '<name>'". A
# `utilities` that rewords it drops the hints to the generic line, which the exact-text hint tests catch on a re-pin.
_MISMATCHED_NAME_RE = re.compile(r", got '([a-z0-9-]+)'$")

# A schema error quotes the failing value; a longer detail is cut in the middle, so the pin hint at its end stays.
_MAX_DETAIL_LENGTH = 1000


class SourceInputError(Exception):
    """`source-path` is not its document type's contract; the message is the one line the run fails with."""


def read_source(document_type: DocumentType, source_path: str) -> SourceDocument:
    """
    Read `source-path` as the contract `document_type` renders.

    @param document_type: The document to render.
    @param source_path: The `source-path` input, as given.
    @return: The typed contract model `read_artifact` returns.
    @raise SourceInputError: The file is missing, unreadable, not UTF-8 JSON, unloadable, another contract, or invalid.
    """
    expected = CONTRACT_NAMES[document_type]
    # `!r` keeps a path with a line break on the one line the run fails with.
    named = f"Input `{SOURCE_PATH}` is {source_path!r}"
    source = Path(source_path)
    try:
        # A FIFO or a device would block the read or never end it.
        if source.exists() and not (source.is_file() or source.is_dir()):
            raise SourceInputError(f"{named}, not a regular file.")
        document = read_artifact(source_path, expected=expected)
    except ContractError as error:
        raise SourceInputError(_contract_error_line(named, document_type, error)) from error
    except IsADirectoryError as error:
        raise SourceInputError(f"{named}, a directory, not a JSON file.") from error
    except OSError as error:
        if error.filename is not None and Path(os.fspath(error.filename)) != source:
            # The file was read: the schema of the `expected` version it declares cannot be opened in the library.
            schema_file = _one_line(repr(Path(os.fspath(error.filename)).name))
            raise SourceInputError(
                f"{named}, a `{expected}` version living-doc-utilities {installed_utilities_version()} ships no "
                f"schema for ({schema_file}); check its `schema_version`, or align the pins if the components run "
                "different utilities versions."
            ) from error
        if isinstance(error, FileNotFoundError):
            raise SourceInputError(f"{named}, which does not exist.") from error
        raise SourceInputError(f"{named}, which cannot be read: {error.strerror}.") from error
    except UnicodeDecodeError as error:
        raise SourceInputError(f"{named}, which is not UTF-8 text: {error.reason} at byte {error.start}.") from error
    except json.JSONDecodeError as error:
        raise SourceInputError(
            f"{named}, which is not JSON: {error.msg} at line {error.lineno}, column {error.colno}."
        ) from error
    except RecursionError as error:
        raise SourceInputError(f"{named}, which is nested too deeply to read.") from error
    except ValueError as error:
        # JSON can still fail to load: an integer past Python's digit limit, or a value a contract model's own check
        # cannot report. CPython's advice to raise the limit is not the action user's to take.
        detail = str(error).split("; use sys.set_int_max_str_digits()", 1)[0]
        raise SourceInputError(f"{named}, which cannot be loaded: {_one_line(detail)}.") from error

    # `read_artifact` returns the typed model of the one contract it was asked for, never a dict.
    return cast(SourceDocument, document)


def _contract_error_line(named: str, document_type: DocumentType, error: ContractError) -> str:
    """The one line for a file `read_artifact` rejected: a hint for another pipeline file, else its own message."""
    expected = CONTRACT_NAMES[document_type]
    if error.code is Code.CONTRACT_MISMATCH:
        mismatched = _MISMATCHED_NAME_RE.search(error.message)
        found = mismatched.group(1) if mismatched else ""
        if found in COLLECTOR_CONTRACT_NAMES:
            return (
                f"{named}, a `{found}` collector output; document type `{document_type.value}` reads a "
                f"`{expected}` file, which the `living-doc-toolkit` command `{TOOLKIT_COMMANDS[document_type]}` "
                "writes."
            )
        if found in _DOCUMENT_TYPES_BY_CONTRACT:
            return (
                f"{named}, a `{found}` file, which document type `{_DOCUMENT_TYPES_BY_CONTRACT[found].value}` "
                f"renders; document type `{document_type.value}` reads a `{expected}` file."
            )
    # A model-level failure carries pydantic's multi-line report; the run fails with one line.
    return f"{named}, not a valid `{expected}` file: {_one_line(str(error))}"


def _one_line(text: str) -> str:
    """`text` on one line, at most `_MAX_DETAIL_LENGTH` characters plus the cut mark."""
    line = " ".join(text.split())
    if len(line) <= _MAX_DETAIL_LENGTH:
        return line
    kept = _MAX_DETAIL_LENGTH // 2
    return f"{line[:kept]} … {line[-kept:]}"
