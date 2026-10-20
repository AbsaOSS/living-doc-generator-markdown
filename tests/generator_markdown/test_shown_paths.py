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
The rendering table, checked against itself: each view of each contract shows every field `shown_paths(contract,
view)` names, and none of the view-dependent fields it leaves out. Every value at those paths is first replaced by a
marker found nowhere else, so its presence or absence in the rendered text is unambiguous.
"""

from itertools import count
from typing import Any, Iterator, Literal, get_origin

import pytest
from living_doc_utilities.contracts import generator_ready, ui_test_catalog
from living_doc_utilities.contracts.testing import shown_paths

from tests.samples import CONTRACTS, VIEWS, plain_text, rendered, sample

# A warning's code is looked up in the code registry, so it keeps its own, distinctive, value.
_KEPT_LEAVES = {"code"}
_URL_LEAVES = {"url", "source_url"}


def _leaves(model: Any, path: str) -> list[tuple[Any, str]]:
    """Every (record, field name) a path such as `content.entities[].acceptance_criteria[].aspect[]` names."""
    *parents, leaf = path.split(".")
    nodes = [model]
    for segment in parents:
        name = segment.removesuffix("[]")
        values = [getattr(node, name) for node in nodes]
        nodes = [
            item for value in values if value is not None for item in (value if segment.endswith("[]") else [value])
        ]
    return [(node, leaf.removesuffix("[]")) for node in nodes]


def _is_literal(node: Any, name: str) -> bool:
    return get_origin(type(node).model_fields[name].annotation) is Literal


def _marker(value: Any, name: str, numbers: Iterator[int]) -> Any:
    """A value of the same kind as `value`, found nowhere else in a document."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        n = next(numbers)
        return f"https://zq{n:04d}x.example/" if name in _URL_LEAVES else f"zq{n:04d}x"
    if isinstance(value, int):
        return 7000 + next(numbers)
    if isinstance(value, float):
        return round(60 + next(numbers) / 10, 1)
    if isinstance(value, list):
        return [_marker(item, name, numbers) for item in value]
    if isinstance(value, dict):
        return {_marker(key, name, numbers): _marker(item, name, numbers) for key, item in value.items()}
    raise TypeError(f"no marker for {value!r}")


def _forms(value: Any) -> list[str]:
    """How a value reads in a document."""
    if value is None or value in ("", [], {}):
        return []
    if isinstance(value, float):
        return [f"{value:.1f}"]
    if isinstance(value, (list, tuple)):
        return [form for item in value for form in _forms(item)]
    if isinstance(value, dict):
        return [form for key, item in value.items() for form in _forms(key) + _forms(item)]
    return [str(value)]


def _marked(document: Any, paths: set[str]) -> dict[str, list[str]]:
    """Replace every free value at `paths` with a marker; return each path's values as they would read."""
    numbers = count(1)
    expected: dict[str, list[str]] = {}
    for path in sorted(paths):
        forms = []
        for node, name in _leaves(document, path):
            value = getattr(node, name)
            if name not in _KEPT_LEAVES and not _is_literal(node, name):
                value = _marker(value, name, numbers)
                setattr(node, name, value)
            forms.extend(_forms(value))
        expected[path] = forms
    return expected


def _shows(text: str, form: str) -> bool:
    # A state or status reads as written, with spaces, or as an upper-case badge.
    return any(variant in text for variant in (form, form.replace("_", " "), form.replace("_", " ").upper()))


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("contract_id", CONTRACTS)
def test_a_view_shows_every_field_shown_paths_names_and_no_view_dependent_field_it_leaves_out(contract_id, view):
    # Arrange: the view-dependent fields are those either view names.
    shown = shown_paths(contract_id, view)
    view_dependent = shown_paths(contract_id, "inner") | shown_paths(contract_id, "release")
    document = sample(contract_id, view)
    expected = _marked(document, view_dependent)

    # Act
    text = plain_text(rendered(document))

    # Assert
    for path, forms in expected.items():
        for form in forms:
            if path in shown:
                assert _shows(text, form), f"{view} view lacks {path} = {form!r}"
            else:
                assert form not in text, f"{view} view shows {path} = {form!r}"


@pytest.mark.parametrize("contract_id", [c for c in CONTRACTS if c != ui_test_catalog.CONTRACT_ID])
def test_every_view_dependent_field_holds_a_value_in_the_inner_sample(contract_id):
    # Arrange
    view_dependent = shown_paths(contract_id, "inner") | shown_paths(contract_id, "release")

    # Act
    expected = _marked(sample(contract_id, "inner"), view_dependent)

    # Assert: the check above tests no path vacuously.
    assert [path for path, forms in expected.items() if not forms] == []


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize(
    ("contract_id", "records"),
    [(generator_ready.CONTRACT_ID, "content.entities[]"), (ui_test_catalog.CONTRACT_ID, "feature_files[].unlinked[]")],
)
def test_a_records_native_type_and_tracker_state_are_never_shown(contract_id, view, records):
    # Arrange: the table's last row hides both in both views.
    document = sample(contract_id, view)
    expected = _marked(document, {f"{records}.source_ref.native_type", f"{records}.source_ref.tracker_state"})

    # Act
    text = plain_text(rendered(document))

    # Assert
    forms = [form for path_forms in expected.values() for form in path_forms]
    assert forms
    assert [form for form in forms if form in text] == []
