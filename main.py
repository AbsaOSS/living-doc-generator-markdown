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
It sets up logging, validates the action inputs and reads the input file. Rendering is not implemented yet, so
every run fails.
"""

import logging
import sys

from living_doc_utilities.logging_config import setup_logging

from generator_markdown.action_inputs import ActionInputError, ActionInputs
from generator_markdown.source_reader import SourceInputError, read_source

# A run with valid inputs still fails, so no pipeline mistakes this version for one that wrote a document.
RENDERING_NOT_IMPLEMENTED_MESSAGE = (
    "Rendering is not implemented yet: living-doc-generator-markdown validated its inputs and wrote no document."
)

logger = logging.getLogger(__name__)


def run() -> None:
    """
    Run the Living Documentation (Liv-Doc) Generator for Markdown: validate the inputs, read the input file, then fail.

    @return: None; the run ends with exit code 1, on an invalid input or input file, or because rendering is not
        implemented yet.
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
    logger.error("%s", RENDERING_NOT_IMPLEMENTED_MESSAGE)
    sys.exit(1)


if __name__ == "__main__":
    run()
