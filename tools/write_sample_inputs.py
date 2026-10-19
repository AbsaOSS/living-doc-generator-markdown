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
Writes `living-doc-utilities`' full sample of each named contract into a directory, as `<contract name>.json`: the
integration jobs' inputs, and a debug run's.
"""

import importlib
import sys
from pathlib import Path

from living_doc_utilities.contracts import registry
from living_doc_utilities.contracts.io import write_artifact
from living_doc_utilities.contracts.testing import full_sample

# Every contract the installed `living-doc-utilities` knows, by name.
CONTRACT_NAMES = sorted({contract_id.rsplit("-v", 1)[0] for contract_id in registry.CONTRACTS})


def write_samples(directory: Path, contract_names: list[str]) -> list[Path]:
    """
    Write the full sample of each named contract into `directory`.

    @param directory: Where the files land; created when missing.
    @param contract_names: Contract names, such as `generator-ready`; each is written at its current version.
    @return: The written files, in the order named.
    """
    written = []
    for name in contract_names:
        contract = importlib.import_module(f"living_doc_utilities.contracts.{name.replace('-', '_')}")
        path = directory / f"{name}.json"
        write_artifact(full_sample(contract.CONTRACT_ID), path)
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    """
    Write the samples the arguments name: a directory, then one or more contract names.

    @param argv: The command-line arguments after the script name.
    @return: 0 when every sample was written, 2 on a usage error.
    """
    if len(argv) < 2 or any(name not in CONTRACT_NAMES for name in argv[1:]):
        print(
            "usage: write_sample_inputs.py <directory> <contract-name>...; "
            f"contract names: {', '.join(CONTRACT_NAMES)}",
            file=sys.stderr,
        )
        return 2
    for path in write_samples(Path(argv[0]), argv[1:]):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
