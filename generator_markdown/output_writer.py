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
The generator's one write: the document and its run report into `output-path`, named by document type.
"""

import json
from pathlib import Path
from typing import Any

from generator_markdown.action_inputs import OUTPUT_PATH, DocumentType


class OutputError(Exception):
    """`output-path` cannot be written; the message is the one line the run fails with."""


def document_file_name(document_type: DocumentType) -> str:
    """The document's file name: `<document-type>.md`."""
    return f"{document_type.value}.md"


def run_report_file_name(document_type: DocumentType) -> str:
    """The run report's file name: `<document-type>.run-report.json`."""
    return f"{document_type.value}.run-report.json"


def write_output(output_path: str, document_type: DocumentType, markdown: str, report: dict[str, Any]) -> list[Path]:
    """
    Write the document and its run report into `output_path`, creating the directory when missing.

    @param output_path: The resolved `output-path` directory.
    @param document_type: The rendered document type, which names both files.
    @param markdown: The document.
    @param report: The run report.
    @return: The document's path, then the run report's.
    @raise OutputError: A file or the directory cannot be written.
    """
    directory = Path(output_path)
    written = [directory / document_file_name(document_type), directory / run_report_file_name(document_type)]
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # Explicit newline: text mode would write CRLF on Windows.
        written[0].write_text(markdown, encoding="utf-8", newline="\n")
        written[1].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    except OSError as error:
        # `!r` keeps a path with a line break on the one line the run fails with.
        raise OutputError(
            f"Input `{OUTPUT_PATH}` is {output_path!r}, which cannot be written: {error.strerror or error}."
        ) from error
    return written
