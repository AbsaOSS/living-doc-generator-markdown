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
import os
from pathlib import Path

import pytest
from living_doc_utilities.contracts import generator_ready
from living_doc_utilities.contracts.io import write_artifact
from living_doc_utilities.contracts.testing import full_sample


@pytest.fixture(autouse=True)
def _clear_action_inputs(monkeypatch):
    # No action input leaks in from the shell, so every input a test does not set reads as unset.
    for name in [name for name in os.environ if name.startswith("INPUT_")]:
        monkeypatch.delenv(name)


@pytest.fixture(name="write_sample")
def _write_sample(tmp_path):
    """Return a writer of `living-doc-utilities`' full sample of a contract; a relative path lands in `tmp_path`."""

    def write(contract_id: str, path: str | Path) -> Path:
        destination = tmp_path / path
        write_artifact(full_sample(contract_id), destination)
        return destination

    return write


@pytest.fixture(name="valid_inputs")
def _valid_inputs(monkeypatch, tmp_path, write_sample):
    """Set the two required inputs to valid values, with a real `generator-ready` file as the source, and run from
    `tmp_path` so relative paths resolve there."""
    monkeypatch.chdir(tmp_path)
    write_sample(generator_ready.CONTRACT_ID, "generator-ready.json")
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", "technical-project")
    monkeypatch.setenv("INPUT_SOURCE_PATH", "generator-ready.json")
    return tmp_path
