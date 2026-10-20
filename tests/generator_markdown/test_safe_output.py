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
Safe output: a hostile input, built from `full_sample()`, renders no raw HTML and no link `url_policy.safe_href`
rejects, and no authored value becomes a heading, a list, a link or any other Markdown block.
"""

from itertools import count
from typing import Any, Iterator, Literal, get_origin

import pytest
from living_doc_utilities.authoring.url_policy import safe_href
from living_doc_utilities.contracts import generator_ready
from pydantic import BaseModel

from tests.samples import CONTRACTS, VIEWS, heading_anchors, heading_texts, rendered, sample, tokens

MARKER = "INJECTED"

# Authored text that would be markup if it reached the Markdown as written: raw HTML, links of every scheme, and
# block syntax at a line start, in one line and across lines.
HOSTILE_TEXTS = [
    f"# {MARKER}-HEADING <script>alert(1)</script>",
    f"- {MARKER}-ITEM <img src=x onerror=alert(1)>",
    f"1. {MARKER}-ITEM [{MARKER}-LINK](javascript:alert(1))",
    f'[{MARKER}-LINK](https://evil.example) <a href="data:text/html,x">{MARKER}-LINK</a>',
    f"Text\n\n# {MARKER}-HEADING\n\n- {MARKER}-ITEM\n\n    {MARKER}-CODE\n\n> {MARKER}-QUOTE\n\n---",
    f"![{MARKER}-IMAGE](https://evil.example/x.png) <https://evil.example> <javascript:alert(1)>",
    f"Parent <b>x</b>\n  - <script>{MARKER}</script>\n# {MARKER}-HEADING\n  - [{MARKER}-LINK](../relative)",
    f'{{: onclick="alert(1)"}} | {MARKER} | cell |\n|---|---|\n```\n{MARKER}-FENCE\n```',
    f"[{MARKER}-REF]: javascript:alert(1)\n\n[{MARKER}-REF]",
]
HOSTILE_URLS = [
    "javascript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "../relative/path",
    "//evil.example/protocol-relative",
    "https:hostless",
    " JaVaScRiPt:alert(1)",
    "vbscript:msgbox(1)",
    "https://example.com/ok) [INJECTED-LINK](javascript:alert(1)",
]

# Fields the presentation keys on: ids and relations, which anchors and links are built from, and the warning code
# it looks up. Literal-typed fields keep their value too.
_KEPT = {
    "schema_version",
    "code",
    "entity_id",
    "id",
    "ac_id",
    "scenario_id",
    "parent",
    "superseded_by",
    "user_stories",
    "functionalities",
    "feature_dependencies",
    "version",
    "removal_planned",
    "keyword",
}
_URLS = {"url", "source_url", "source"}


def hostile(document: Any) -> Any:
    """A copy of `document` with every other text and URL field hostile."""
    copy = document.model_copy(deep=True)
    _make_hostile(copy, count(), count())
    return copy


def _make_hostile(model: BaseModel, texts: Iterator[int], urls: Iterator[int]) -> None:
    for name, field in type(model).model_fields.items():
        if name in _KEPT or get_origin(field.annotation) is Literal:
            continue
        setattr(model, name, _hostile_value(name, getattr(model, name), texts, urls))


def _hostile_value(name: str, value: Any, texts: Iterator[int], urls: Iterator[int]) -> Any:
    if isinstance(value, BaseModel):
        _make_hostile(value, texts, urls)
        return value
    if isinstance(value, str):
        if name in _URLS:
            return HOSTILE_URLS[next(urls) % len(HOSTILE_URLS)]
        return HOSTILE_TEXTS[next(texts) % len(HOSTILE_TEXTS)]
    if isinstance(value, list):
        return [_hostile_value(name, item, texts, urls) for item in value]
    if isinstance(value, dict):
        return {key: _hostile_value(name, item, texts, urls) for key, item in value.items()}
    return value


@pytest.fixture(name="hostile_markdown", params=[(c, v) for c in CONTRACTS for v in VIEWS], ids=lambda p: "-".join(p))
def _hostile_markdown(request) -> str:
    contract_id, view = request.param
    return rendered(hostile(sample(contract_id, view)), title=HOSTILE_TEXTS[0])


def test_the_hostile_fixture_reaches_every_document(hostile_markdown):
    # Assert: the hostile values are rendered, as text, so the checks below look at them.
    assert MARKER in hostile_markdown


def test_no_raw_html_reaches_the_markdown(hostile_markdown):
    # Assert: every `<` is written as an entity, so no tag can open.
    assert "<" not in hostile_markdown
    assert not [t for t in tokens(hostile_markdown) if t.type in ("html_block", "html_inline")]


def test_every_link_is_one_safe_href_keeps_or_an_entitys_place_in_the_document(hostile_markdown):
    # Arrange
    anchors = heading_anchors(hostile_markdown)
    hrefs = [t.attrGet("href") for t in tokens(hostile_markdown) if t.type == "link_open"]

    # Assert: a hostile URL is never linked; only the relations' anchors are left.
    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in anchors, href
        else:
            assert safe_href(href) == href, href


def test_no_authored_value_becomes_a_heading_a_list_a_link_or_another_block(hostile_markdown):
    # Arrange
    flat = tokens(hostile_markdown)

    # Assert: a template's heading may hold an authored value, as text; an injected one would start with the marker.
    assert not [text for text in heading_texts(hostile_markdown) if text.startswith(MARKER)]
    assert not [t for t in flat if t.type in ("image", "hr", "blockquote_open", "code_block", "fence")]
    # A template's list item or link may hold an authored value; an injected one would start with the marker.
    following = [flat[index + 1] for index, token in enumerate(flat[:-1]) if token.type == "link_open"]
    following += [flat[index + 2] for index, token in enumerate(flat[:-2]) if token.type == "list_item_open"]
    assert not [t.content for t in following if t.content.startswith(MARKER)]


def test_relations_still_link_in_a_hostile_document():
    # Act
    markdown = rendered(hostile(sample(generator_ready.CONTRACT_ID)))

    # Assert
    assert "- **User stories:** [US-001](#us-001)\n" in markdown


def test_a_hostile_entity_id_gives_a_plain_anchor_and_an_escaped_heading():
    # Arrange
    document = sample(generator_ready.CONTRACT_ID)
    document.content.entities[0].entity_id = "US-1 <script>x</script>](javascript:alert(1))"
    document.content.entities[2].user_stories = [document.content.entities[0].entity_id]

    # Act
    markdown = rendered(document)

    # Assert
    assert "### US-1 &lt;script&gt;x&lt;/script&gt;\\](javascript:alert(1))\n" in markdown
    assert "(#us-1-scriptxscriptjavascriptalert1)" in markdown
    assert "us-1-scriptxscriptjavascriptalert1" in heading_anchors(markdown)
