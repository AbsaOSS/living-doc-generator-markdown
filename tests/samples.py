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
The inputs the rendering tests build from `living-doc-utilities`' full samples, each view's, and the Markdown parser
they read a rendered document with.
"""

import re
from typing import Any

from living_doc_utilities.contracts import coverage_matrix, generator_ready, ui_test_catalog
from living_doc_utilities.contracts.registry import ContractResult
from living_doc_utilities.contracts.testing import full_sample
from markdown_it import MarkdownIt
from markdown_it.token import Token

from generator_markdown.presentation import present
from generator_markdown.renderer import render

DOCUMENT_TYPES = {
    generator_ready.CONTRACT_ID: "technical-project",
    ui_test_catalog.CONTRACT_ID: "ui-test-catalog",
    coverage_matrix.CONTRACT_ID: "coverage-matrix",
}
CONTRACTS = list(DOCUMENT_TYPES)
VIEWS = ["inner", "release"]

# What a transform's release filter drops (`living-doc-utilities` rendering.md § Records and presentation).
_RELEASE_DROPS = {"planned", "in_review"}

# CommonMark plus the GFM tables the coverage matrix writes.
_MARKDOWN = MarkdownIt("commonmark").enable("table")


def _keep_every_link(_url: str) -> bool:
    return True


# markdown-it drops a `javascript:`, `vbscript:`, `file:` or `data:` link before it tokenizes it; a test must see every
# link the Markdown holds.
_MARKDOWN.validateLink = _keep_every_link


def sample(contract_id: str, view: str = "inner") -> ContractResult:
    """`full_sample(contract_id)` as a transform writes it for `view`."""
    document = full_sample(contract_id)
    return release(document) if view == "release" else document


def release(document: Any) -> Any:
    """
    The release input of an inner one: a `generator-ready` drops its planned and in_review entities and criteria, a
    Feature by its derived state; a coverage matrix and a catalog only declare the view, as the release filter
    changes no row of theirs.
    """
    payload = document.model_dump(mode="json")
    payload["document"]["view"] = "release"
    if document.schema_version == generator_ready.CONTRACT_ID:
        kept = [entity for entity in payload["content"]["entities"] if entity["state"] not in _RELEASE_DROPS]
        for entity in kept:
            entity["acceptance_criteria"] = [
                criterion for criterion in entity["acceptance_criteria"] if criterion["state"] not in _RELEASE_DROPS
            ]
        payload["content"]["entities"] = kept
        selection = payload["document"]["selection_summary"]
        selection["included_entities"] = len(kept)
        selection["excluded_entities"] = selection["total_entities"] - len(kept)
        included = sum(len(entity["acceptance_criteria"]) for entity in kept)
        selection["included_acceptance_criteria"] = included
        selection["excluded_acceptance_criteria"] = selection["total_acceptance_criteria"] - included
    # Validated: the release input is a contract file a transform could write.
    return type(document).model_validate(payload)


def rendered(document: Any, title: str = "") -> str:
    """`document` rendered as its document type's Markdown."""
    return render(present(document, title), DOCUMENT_TYPES[document.schema_version])


def tokens(markdown: str) -> list[Token]:
    """The block and inline tokens of `markdown`, flattened in document order."""
    flat: list[Token] = []
    for token in _MARKDOWN.parse(markdown):
        flat.append(token)
        flat.extend(token.children or [])
    return flat


def heading_texts(markdown: str) -> list[str]:
    """Every heading's text, as a renderer shows it."""
    parsed = _MARKDOWN.parse(markdown)
    return [_plain(parsed[i + 1]) for i, token in enumerate(parsed) if token.type == "heading_open"]


def heading_anchors(markdown: str) -> set[str]:
    """The anchors a renderer derives from the headings: GitHub's rule, lower case without punctuation."""
    return {re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-") for text in heading_texts(markdown)}


def plain_text(markdown: str) -> str:
    """Everything a reader sees, one line per block, with every link's destination after it."""
    lines = []
    for token in _MARKDOWN.parse(markdown):
        if token.type == "inline":
            lines.append(_plain(token))
    return "\n".join(lines)


def _plain(inline: Token) -> str:
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type == "softbreak":
            parts.append(" ")
        elif child.type == "link_open":
            parts.append(f"<{child.attrGet('href')}>")
    return "".join(parts)
