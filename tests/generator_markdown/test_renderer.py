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
import pytest
from living_doc_utilities.contracts import coverage_matrix
from living_doc_utilities.contracts.codes import Code, ContractError

from generator_markdown import renderer
from generator_markdown.presentation import Link, present
from generator_markdown.renderer import TEMPLATES_DIR, escape, render
from tests.samples import DOCUMENT_TYPES, plain_text, sample


def _template_root(tmp_path, document_type: str, template: str):
    (tmp_path / document_type).mkdir()
    (tmp_path / document_type / "document.md.j2").write_text(template, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("text", "markdown"),
    [
        ("plain text, version 1.4.0 (v1.0.0 - active)", "plain text, version 1.4.0 (v1.0.0 - active)"),
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ("[x](javascript:alert(1))", "\\[x\\](javascript:alert(1))"),
        ("# heading", "\\# heading"),
        ("- item", "\\- item"),
        ("+ item", "\\+ item"),
        ("1. item", "1\\. item"),
        ("12) item", "12\\) item"),
        ("2026-06-01", "2026-06-01"),
        ("a\nb\r\n\n  c", "a b c"),
        ("*a* _b_ `c` ~d~ {e} |f| \\g & h", "\\*a\\* \\_b\\_ \\`c\\` \\~d\\~ \\{e\\} \\|f\\| \\\\g &amp; h"),
    ],
)
def test_escape_keeps_a_value_on_one_line_as_text(text, markdown):
    # Act & Assert
    assert escape(text) == markdown


@pytest.mark.parametrize(
    "text", ["<b>bold</b>", "[x](javascript:alert(1))", "# heading", "- item", "1. item", "*a* _b_ `c`", "&amp;"]
)
def test_an_escaped_value_reads_as_written_in_a_markdown_renderer(text):
    # Act
    shown = plain_text(f"{escape(text)}\n")

    # Assert
    assert shown == text


def test_a_template_reading_a_key_the_model_lacks_fails_with_template_key_missing(tmp_path):
    # Arrange
    root = _template_root(tmp_path, "coverage-matrix", "# {{ document.title }}\n\n{{ document.owner }}\n")

    # Act
    with pytest.raises(ContractError) as error:
        render(present(sample(coverage_matrix.CONTRACT_ID)), "coverage-matrix", root)

    # Assert: one line, never an empty section.
    assert error.value.code is Code.TEMPLATE_KEY_MISSING
    assert str(error.value) == (
        "[TEMPLATE_KEY_MISSING] template 'coverage-matrix/document.md.j2' reads a key its model lacks: "
        "'generator_markdown.presentation.CoverageMatrix object' has no attribute 'owner'"
    )


def test_a_template_testing_a_key_the_model_lacks_fails_too(tmp_path):
    # Arrange
    root = _template_root(tmp_path, "coverage-matrix", "{% if document.owner %}x{% endif %}\n")

    # Act
    with pytest.raises(ContractError) as error:
        render(present(sample(coverage_matrix.CONTRACT_ID)), "coverage-matrix", root)

    # Assert
    assert error.value.code is Code.TEMPLATE_KEY_MISSING


def test_a_template_printing_a_value_the_model_leaves_empty_fails_with_template_key_missing(tmp_path):
    # Arrange: the release view has no planned work summary.
    root = _template_root(tmp_path, "coverage-matrix", "## Planned work\n\n{{ document.planned }}\n")

    # Act
    with pytest.raises(ContractError) as error:
        render(present(sample(coverage_matrix.CONTRACT_ID, "release")), "coverage-matrix", root)

    # Assert
    assert error.value.code is Code.TEMPLATE_KEY_MISSING
    assert "a template printed a value the model leaves empty" in str(error.value)


@pytest.mark.parametrize(
    ("link", "markdown"),
    [
        (Link(text="a [b]", href="https://example.com/a b(c)"), "[a \\[b\\]](https://example.com/a%20b%28c%29)"),
        (Link(text="US-001", anchor="us-001"), "[US-001](#us-001)"),
        (Link(text="FEAT-002"), "FEAT-002"),
    ],
)
def test_a_link_is_written_with_its_destination_encoded(tmp_path, link, markdown):
    # Arrange
    root = _template_root(tmp_path, "coverage-matrix", "{{ link | link }}\n")

    # Act
    text = _render_with(root, link=link)

    # Assert
    assert text == f"{markdown}\n"


def test_an_anchor_that_no_entity_id_gives_is_refused(tmp_path):
    # Arrange
    root = _template_root(tmp_path, "coverage-matrix", "{{ link | link }}\n")

    # Act & Assert
    with pytest.raises(ValueError, match="not an entity anchor"):
        _render_with(root, link=Link(text="x", anchor="x)(javascript:alert(1)"))


@pytest.mark.parametrize(("text", "span"), [("ACTIVE", "`ACTIVE`"), ("a`b", "``a`b``"), ("`a", "`` `a ``")])
def test_a_code_span_is_delimited_by_more_backticks_than_it_holds(tmp_path, text, span):
    # Arrange
    root = _template_root(tmp_path, "coverage-matrix", "{{ text | code }}\n")

    # Act & Assert
    assert _render_with(root, text=text) == f"{span}\n"
    assert plain_text(span) == text


@pytest.mark.parametrize("contract_id", list(DOCUMENT_TYPES))
def test_a_document_ends_in_one_line_break_with_no_trailing_space_or_run_of_blank_lines(contract_id):
    # Act
    markdown = render(present(sample(contract_id)), DOCUMENT_TYPES[contract_id])

    # Assert
    assert markdown.endswith("\n") and not markdown.endswith("\n\n")
    assert "\n\n\n" not in markdown
    assert all(line == line.rstrip() for line in markdown.splitlines())


def test_every_document_type_has_its_template():
    # Assert
    assert sorted(path.name for path in TEMPLATES_DIR.iterdir()) == sorted(DOCUMENT_TYPES.values())
    assert all((TEMPLATES_DIR / name / "document.md.j2").is_file() for name in DOCUMENT_TYPES.values())


def _render_with(root, **context) -> str:
    # The renderer's own environment, filters and escaping included, on a context of the test's choosing.
    return renderer._environment(root).get_template("coverage-matrix/document.md.j2").render(**context)
