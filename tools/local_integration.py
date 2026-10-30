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
The Python half of `local-integration.sh`: the report on one document the generator rendered - its input re-read with
`read_artifact`, then the input's contract and producer, the document's view and title, the time the run took, the
sizes, the run report's counts and the length of each render manifest list, and the input's warnings by code. Runs in
the script's venv, which holds `requirements.txt` alone, so it imports `living_doc_utilities` and the standard library
only: never `generator_markdown`, the code it checks.
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import Any, Optional

from living_doc_utilities.contracts.codes import ContractError
from living_doc_utilities.contracts.envelope import ContractWarning
from living_doc_utilities.contracts.io import read_artifact

# How many occurrences of each warning code the report lists; the count covers them all.
FIRST_OCCURRENCES = 10

# The `living-doc-toolkit` output each document type renders, by contract name: the generator's own table, which this
# helper cannot import.
CONTRACTS = {
    "technical-project": "generator-ready",
    "ui-test-catalog": "ui-test-catalog",
    "coverage-matrix": "coverage-matrix",
}

# The run report's counts: the cardinality keys `write_artifact` computes from an input's records.
COUNTED = ("entities", "entities_by_type", "acceptance_criteria", "scenarios", "warnings_by_code")

# The render manifest's lists, in the run report's order.
MANIFEST_LISTS = ("entities", "acceptance_criteria", "aspects", "badges", "scenarios", "not_loaded")

# The document types whose manifest lists each counted entity and criterion once. The catalog's does not: its counts
# hold no entity or criterion, and count a scenario in each group that lists it, where its manifest lists it once.
MANIFEST_MATCHES_COUNTS = {"technical-project", "coverage-matrix"}


class NotRendered(Exception):
    """The document or its run report is missing or empty, or the run report disagrees with the input."""


def _printable(line: str) -> str:
    """
    One report line as the terminal shows it, a control character spelled out (`\\n`, `\\x1b`): an input is another
    component's file, and its text must neither forge a report line nor drive the terminal.
    """
    return "".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii") for char in line)


def _counts(value: Any) -> str:
    """A count on one line: a number as it is, a mapping as sorted `key=count` pairs, an absent one as `-`."""
    if isinstance(value, dict):
        return ", ".join(f"{key}={count}" for key, count in sorted(value.items())) or "-"
    return "-" if value is None else str(value)


def _occurrence(warning: ContractWarning) -> str:
    """Where one warning was raised and what it says: `<path>:<line> <entity>/<ac> <message>`."""
    where = warning.path or warning.context or "-"
    if warning.line_no is not None:
        where = f"{where}:{warning.line_no}"
    subject = "/".join(part for part in (warning.entity_id, warning.ac_id) if part)
    return " ".join(part for part in (where, subject, warning.message) if part)


def warnings_by_code(warnings: Sequence[ContractWarning], first: int = FIRST_OCCURRENCES) -> list[str]:
    """
    The warnings grouped by code, codes sorted: each code's count, then its first occurrences in input order.

    @param warnings: The input's warnings.
    @param first: How many occurrences of each code to list.
    @return: The report lines.
    """
    grouped: dict[str, list[ContractWarning]] = {}
    for warning in warnings:
        grouped.setdefault(warning.code, []).append(warning)
    lines = [f"  warnings: {len(warnings)}"]
    for code in sorted(grouped):
        occurrences = grouped[code]
        lines.append(f"    {code}: {len(occurrences)}")
        lines.extend(f"      {_occurrence(warning)}" for warning in occurrences[:first])
        if len(occurrences) > first:
            lines.append(f"      ... and {len(occurrences) - first} more")
    return lines


def _written(path: str, what: str) -> int:
    """The size of a file the generator writes; a missing or empty one fails."""
    if not os.path.isfile(path):
        raise NotRendered(f"the {what} '{path}' is missing")
    size = os.path.getsize(path)
    if size == 0:
        raise NotRendered(f"the {what} '{path}' is empty")
    return size


def _run_report(path: str) -> dict[str, Any]:
    """The run report at `path`, holding the counts and the render manifest lists the checks read."""
    with open(path, encoding="utf-8") as file:
        try:
            run_report = json.load(file)
        except json.JSONDecodeError as error:
            raise NotRendered(f"the run report '{path}' is not JSON: {error}") from error
    if not (
        isinstance(run_report, dict)
        and isinstance(run_report.get("counts"), dict)
        and isinstance(run_report.get("render_manifest"), dict)
        and all(isinstance(run_report["render_manifest"].get(name), list) for name in MANIFEST_LISTS)
    ):
        raise NotRendered(f"the run report '{path}' holds no counts or no render manifest")
    return run_report


def _check(document_type: str, source: Any, run_report: dict[str, Any]) -> None:
    """
    Hold the run report to its input: its counts are the input's `metadata.stats.cardinality`, its view and its
    manifest's are the input's `document.view`, and a technical project's or matrix's manifest lists what it counts.
    """
    cardinality = source.metadata.stats.cardinality.model_dump()
    counts = run_report["counts"]
    differing = [
        f"{name} {_counts(counts.get(name))}, the input's {_counts(cardinality[name])}"
        for name in COUNTED
        if counts.get(name) != cardinality[name]
    ]
    if differing:
        raise NotRendered(
            f"the run report's counts differ from the input's metadata.stats.cardinality: {'; '.join(differing)}"
        )
    manifest = run_report["render_manifest"]
    view = source.document.view
    if run_report.get("view") != view or manifest.get("view") != view:
        raise NotRendered(
            f"the run report's view is {run_report.get('view')!r}, its manifest's {manifest.get('view')!r}; "
            f"the input's is {view!r}"
        )
    if document_type in MANIFEST_MATCHES_COUNTS:
        for name in ("entities", "acceptance_criteria"):
            if len(manifest[name]) != counts[name]:
                raise NotRendered(
                    f"the render manifest lists {len(manifest[name])} {name} where the run report counts {counts[name]}"
                )


def report(document_type: str, input_path: str, output_dir: str, elapsed_ms: int) -> list[str]:
    """
    Re-read one document's input with `read_artifact`, check the document and its run report against it, and
    describe them.

    @param document_type: The rendered document type, e.g. `technical-project`.
    @param input_path: The input file the document was rendered from.
    @param output_dir: The directory the generator wrote the document and its run report into.
    @param elapsed_ms: How long the generator's run took, in milliseconds.
    @return: The report lines.
    @raise ContractError: When the input fails its document type's contract.
    @raise NotRendered: When the document or its run report is missing or empty, or the run report disagrees with the
        input.
    @raise OSError: When a file cannot be read.
    @raise ValueError: When the input is not JSON.
    """
    source = read_artifact(input_path, CONTRACTS[document_type])
    document_path = os.path.join(output_dir, f"{document_type}.md")
    run_report_path = os.path.join(output_dir, f"{document_type}.run-report.json")
    document_size = _written(document_path, "document")
    run_report_size = _written(run_report_path, "run report")
    run_report = _run_report(run_report_path)
    _check(document_type, source, run_report)
    producer = source.metadata.producer
    manifest = run_report["render_manifest"]
    return [
        f"{document_type}: {document_path}",
        f"  input: {source.schema_version}, valid (read_artifact)",
        f"  producer: {producer.name} {producer.version}, living-doc-utilities {producer.utilities_version}",
        f"  view: {run_report['view']}",
        f"  title: {run_report.get('title')}",
        f"  time: {elapsed_ms / 1000:.2f} s",
        f"  size: {document_size} bytes, run report {run_report_size} bytes",
        "  counts:",
        *(f"    {name}: {_counts(run_report['counts'][name])}" for name in COUNTED),
        "  render_manifest:",
        *(f"    {name}: {len(manifest[name])}" for name in MANIFEST_LISTS),
        *warnings_by_code(source.warnings),
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    The command line `local-integration.sh` calls: `report` checks one document and prints its report.

    @param argv: The arguments; the process's own when None.
    @return: The process exit code: 0 on success, 1 when the document, its run report or its input fails a check.
    """
    parser = argparse.ArgumentParser(prog="python -m tools.local_integration")
    commands = parser.add_subparsers(dest="command", required=True)
    document = commands.add_parser("report", help="check one rendered document and print its report")
    document.add_argument("document_type", choices=sorted(CONTRACTS))
    document.add_argument("input")
    document.add_argument("output_dir")
    document.add_argument("elapsed_ms", type=int)
    args = parser.parse_args(argv)

    try:
        lines = report(args.document_type, args.input, args.output_dir, args.elapsed_ms)
    except NotRendered as e:
        failure = str(e)
    except ContractError as e:
        failure = f"the input is not valid: {e}"
    except (OSError, ValueError) as e:
        failure = f"cannot be read: {e}"
    else:
        print("\n".join(_printable(line) for line in lines))
        return 0
    print(_printable(f"{args.document_type}: {failure}"), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
