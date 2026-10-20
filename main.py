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
This module contains the main script for the Living Documentation Generator for Markdown GH Action.
It sets up logging, validates the action inputs, reads the input file, renders the document by the view the input
declares, and writes the document and its run report into `output-path`.
"""

import logging
import sys

from living_doc_utilities.contracts.codes import ContractError
from living_doc_utilities.github.utils import set_action_output
from living_doc_utilities.logging_config import setup_logging

from generator_markdown.action_inputs import OUTPUT_PATH, ActionInputError, ActionInputs
from generator_markdown.output_writer import OutputError, document_file_name, write_output
from generator_markdown.presentation import present
from generator_markdown.renderer import render
from generator_markdown.run_report import run_report
from generator_markdown.source_reader import SourceInputError, read_source

logger = logging.getLogger(__name__)


def run() -> None:
    """
    Run the Living Documentation (Liv-Doc) Generator for Markdown: validate the inputs, read the input file, render
    the document and write it with its run report.

    @return: None; the run ends with exit code 1 on an invalid input or input file, a template missing a key, or an
        output it cannot write, and with exit code 0 once the document and its run report are written.
    """
    setup_logging()
    logger.info("Liv-Doc generator for Markdown - starting.")

    try:
        inputs = ActionInputs.from_environment()
    except ActionInputError as error:
        logger.error("%s", error)
        sys.exit(1)

    logger.info(
        "Liv-Doc generator for Markdown - inputs valid: document type `%s`, source `%s`, output `%s`.",
        inputs.document_type.value,
        inputs.source_path,
        inputs.output_path,
    )

    try:
        document = read_source(inputs.document_type, inputs.source_path)
    except SourceInputError as error:
        logger.error("%s", error)
        sys.exit(1)

    logger.info("Liv-Doc generator for Markdown - input read: `%s`.", document.schema_version)
    producer = document.metadata.producer
    # `%r`: the file's own values stay on one log line.
    logger.debug(
        "Liv-Doc generator for Markdown - input written by %r %r with living-doc-utilities %r.",
        producer.name,
        producer.version,
        producer.utilities_version,
    )

    presentation = present(document, inputs.document_title)
    try:
        markdown = render(presentation, inputs.document_type.value)
    except ContractError as error:
        logger.error("%s", error)
        sys.exit(1)

    report = run_report(inputs.document_type, document, presentation, document_file_name(inputs.document_type))
    try:
        written = write_output(inputs.output_path, inputs.document_type, markdown, report)
    except OutputError as error:
        logger.error("%s", error)
        sys.exit(1)
    for path in written:
        logger.info("Liv-Doc generator for Markdown - written: `%s`.", path)

    try:
        set_action_output(OUTPUT_PATH, inputs.output_path)
    except KeyError:
        # A run outside GitHub Actions has no `GITHUB_OUTPUT` to append to.
        logger.info("Liv-Doc generator for Markdown - no `GITHUB_OUTPUT`: the `%s` output is not set.", OUTPUT_PATH)
    except OSError as error:
        logger.error("Liv-Doc generator for Markdown - the `%s` output cannot be set: %s.", OUTPUT_PATH, error)
        sys.exit(1)

    logger.info("Liv-Doc generator for Markdown - finished: %s view of `%s`.", presentation.view, inputs.output_path)


if __name__ == "__main__":
    run()
