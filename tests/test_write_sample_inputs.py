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
from living_doc_utilities.contracts import coverage_matrix, generator_ready
from living_doc_utilities.contracts.io import read_artifact

from tools.write_sample_inputs import main


def test_each_named_contract_is_written_as_its_sample_and_reads_back(tmp_path, capsys):
    # Act
    status = main([str(tmp_path / "inputs"), "generator-ready", "coverage-matrix"])

    # Assert
    assert status == 0
    written = [tmp_path / "inputs" / "generator-ready.json", tmp_path / "inputs" / "coverage-matrix.json"]
    assert capsys.readouterr().out.splitlines() == [str(path) for path in written]
    assert read_artifact(written[0], expected="generator-ready").schema_version == generator_ready.CONTRACT_ID
    assert read_artifact(written[1], expected="coverage-matrix").schema_version == coverage_matrix.CONTRACT_ID


@pytest.mark.parametrize("names", [[], ["generator-redy"], ["generator-ready", "registry"]])
def test_a_call_without_a_known_contract_name_is_a_usage_error_and_writes_nothing(tmp_path, capsys, names):
    # Act
    status = main([str(tmp_path / "inputs"), *names])

    # Assert
    assert status == 2
    assert capsys.readouterr().err.startswith("usage: write_sample_inputs.py <directory> <contract-name>...")
    assert list(tmp_path.iterdir()) == []
