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
The Markdown renderer: it renders a presentation model through the templates under `templates/<document-type>/`. Every
value a template prints is escaped, so authored text reaches the Markdown as text, never as HTML, a link, a heading or
a list; only this module's filters write Markdown syntax around a value. GitHub still links a bare address in authored
text by itself, to the address as written.
"""

import re
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, UndefinedError
from living_doc_utilities.contracts.codes import Code, ContractError

from generator_markdown.presentation import Link, Presentation

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

# Every ASCII character that opens Markdown inline syntax. `<`, `>` and `&` become entities, which every renderer
# reads as text, so no HTML tag and no autolink can form; so do `|` and `~`, which Python-Markdown cannot escape with
# a backslash; the rest take a backslash.
_ESCAPES = str.maketrans(
    {
        "\\": "\\\\",
        "`": "\\`",
        "*": "\\*",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "[": "\\[",
        "]": "\\]",
        "#": "\\#",
        "|": "&#124;",
        "~": "&#126;",
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
    }
)

# GitHub links a bare `http:`, `https:`, `ftp:` or `www.` address it finds in the written line, escapes included, so an
# escaped address would show its backslashes and link elsewhere. An entity for its `:` or `.` keeps it from that pass;
# GitHub then links the address as written.
_AUTOLINK_RE = re.compile(r"(?P<scheme>https?|ftp):|(?P<www>www)\.", re.IGNORECASE)

# A value can open a block, as a list item's text or a paragraph: a leading `-` or `+` would open a list or a
# thematic break, and `1.` or `1)` before a space a numbered list.
_BLOCK_START_RE = re.compile(r"^(?:(?P<marker>[-+])|(?P<number>\d{1,9})(?P<delimiter>[.)])(?= |$))")

# What a link destination keeps as it is; anything else, `(`, `)` and spaces included, is percent-encoded.
_URL_SAFE = ":/?#@!$&*+,;=%-._~"

_ANCHOR_RE = re.compile(r"^[a-z0-9_-]+$")
_EXTRA_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)

# Four spaces nest a list item under a `- ` item in CommonMark and in Python-Markdown alike.
_LIST_INDENT = "    "


class Markdown(str):
    """Markdown this module built; a template prints it as it is."""


def escape(text: str) -> Markdown:
    """
    `text` as Markdown that shows it literally, on one line.

    @param text: Any value from the input.
    @return: The escaped text.
    """
    line = _AUTOLINK_RE.sub(_escape_autolink, " ".join(str(text).split()).translate(_ESCAPES))
    return Markdown(_BLOCK_START_RE.sub(_escape_block_start, line))


def render(presentation: Presentation, document_type: str, templates_dir: Optional[Path] = None) -> str:
    """
    Render a presentation model as a Markdown document.

    @param presentation: What the document shows.
    @param document_type: The `document-type`; its template is `<document_type>/document.md.j2`.
    @param templates_dir: The template root; `TEMPLATES_DIR` when not given.
    @return: The document, ending in one line break.
    @raise ContractError: `TEMPLATE_KEY_MISSING`, when a template reads a key the model lacks or prints an empty one.
    """
    name = f"{document_type}/document.md.j2"
    template = _environment(templates_dir or TEMPLATES_DIR).get_template(name)
    try:
        text = template.render(document=presentation)
    except UndefinedError as error:
        raise ContractError(
            Code.TEMPLATE_KEY_MISSING,
            f"template {name!r} reads a key its model lacks: {' '.join(str(error.message).split())}",
        ) from error
    text = _TRAILING_SPACE_RE.sub("", text)
    return _EXTRA_BLANK_LINES_RE.sub("\n\n", text).strip("\n") + "\n"


def _environment(templates_dir: Path) -> Environment:
    # Jinja's autoescape writes HTML entities and leaves Markdown syntax alone, so `finalize` escapes instead: every
    # printed value goes through `escape` unless one of the filters below built it.
    environment = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,
        finalize=_finalize,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    environment.filters.update(
        {
            "link": _link,
            "links": _links,
            "anchored": _anchored,
            "code": _code,
            "indent": _indent,
        }
    )
    return environment


def _finalize(value: Any) -> Markdown:
    if isinstance(value, Markdown):
        return value
    if value is None:
        # An empty value printed would leave an empty section.
        raise UndefinedError("a template printed a value the model leaves empty")
    return escape(str(value))


def _escape_block_start(match: re.Match[str]) -> str:
    if match.group("marker"):
        return "\\" + match.group("marker")
    return match.group("number") + "\\" + match.group("delimiter")


def _escape_autolink(match: re.Match[str]) -> str:
    if match.group("scheme"):
        return match.group("scheme") + "&#58;"
    return match.group("www") + "&#46;"


def _link(link: Link) -> Markdown:
    """A link to a vetted URL or to an entity's anchor; with neither, its text alone."""
    if link.href is not None:
        # A renderer reads an entity in a destination as its character, `&#64;` as `@`; `&amp;` keeps each `&` one.
        destination = quote(link.href, safe=_URL_SAFE).replace("&", "&amp;")
        return Markdown(f"[{escape(link.text)}]({destination})")
    if link.anchor is not None:
        return _anchored(link.text, link.anchor)
    return escape(link.text)


def _links(links: Iterable[Link]) -> Markdown:
    return Markdown(", ".join(_link(link) for link in links))


def _anchored(text: str, anchor: Optional[str]) -> Markdown:
    """`text` linked to `#anchor`, an anchor the presentation derived from an entity id."""
    if anchor is None:
        raise UndefinedError("a template linked to an anchor the model leaves empty")
    # `str` of a key the model lacks raises `UndefinedError`, so it fails as `TEMPLATE_KEY_MISSING`.
    if not _ANCHOR_RE.match(str(anchor)):
        raise ValueError(f"not an entity anchor: {anchor!r}")
    return Markdown(f"[{escape(text)}](#{anchor})")


def _code(text: str) -> Markdown:
    """A badge or a code as a code span; its delimiter is longer than any backtick run inside it."""
    content = " ".join(str(text).split())
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if content.startswith("`") or content.endswith("`") else ""
    return Markdown(f"{fence}{pad}{content}{pad}{fence}")


def _indent(depth: int) -> Markdown:
    return Markdown(_LIST_INDENT * depth)
