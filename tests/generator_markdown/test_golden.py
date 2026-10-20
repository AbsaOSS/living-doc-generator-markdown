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
Golden snapshots: `full_sample()` of each contract, rendered in each view, compared byte for byte with the committed
document and render manifest. They are what shows a move of the presentation module changes no output.
Regenerate them with `UPDATE_GOLDEN=1 pytest tests/generator_markdown/test_golden.py`, and review the diff.
"""

import json
import os
from pathlib import Path

import pytest

from generator_markdown.presentation import present, render_manifest
from generator_markdown.renderer import render
from tests.samples import CONTRACTS, DOCUMENT_TYPES, VIEWS, sample

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden"


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("contract_id", CONTRACTS)
def test_the_full_sample_renders_as_its_golden_snapshot(contract_id, view):
    # Arrange
    document_type = DOCUMENT_TYPES[contract_id]
    presentation = present(sample(contract_id, view))

    # Act
    snapshots = {
        GOLDEN / document_type / f"{view}.md": render(presentation, document_type),
        GOLDEN
        / document_type
        / f"{view}.render-manifest.json": json.dumps(render_manifest(presentation), indent=2, ensure_ascii=False)
        + "\n",
    }

    # Assert
    for path, text in snapshots.items():
        if os.environ.get("UPDATE_GOLDEN") == "1":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        assert path.read_bytes() == text.encode("utf-8"), f"{path.name} differs; see the module docstring"
