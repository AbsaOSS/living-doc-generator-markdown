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
from living_doc_utilities.contracts import ui_test_catalog

from tests.samples import rendered, sample

CONTRACT = ui_test_catalog.CONTRACT_ID
SCENARIOS = (
    "- **SCN-001** Customer completes checkout with a saved card\n"
    "    - **Covers:** US-001-01 (desktop), US-001-01 (mobile), US-001-04 (card-holder)\n"
    "    - **Tags:** smoke\n"
    "    - **Source:** [GitHub checkout.feature](https://github.com/absaoss/payments-service/issues/checkout.feature)\n"
    "- **SCN-002** Customer completes checkout as a guest\n"
    "    - **Covers:** US-002-01\n"
    "    - **Source:** [AzureDevOps checkout.feature\\#12]"
    "(https://dev.azure.com/absaoss/payments/_workitems/edit/checkout.feature#12)\n"
)


def test_each_feature_files_scenarios_show_linked_to_a_user_story_to_a_functionality_and_unlinked():
    # Act
    markdown = rendered(sample(CONTRACT))

    # Assert
    assert markdown == (
        "# UI test catalog\n\n*View: inner*\n\n## checkout.feature\n\n"
        f"### Linked to a User Story\n\n**US-001**\n\n{SCENARIOS}\n"
        f"### Linked to a Functionality\n\n**FUNC-001**\n\n{SCENARIOS}\n"
        f"### Unlinked\n\n{SCENARIOS}"
    )


def test_no_field_depends_on_the_view():
    # Act
    inner = rendered(sample(CONTRACT, "inner"))
    release = rendered(sample(CONTRACT, "release"))

    # Assert
    assert release == inner.replace("*View: inner*", "*View: release*")


def test_an_empty_group_is_left_out():
    # Arrange
    document = sample(CONTRACT)
    document.feature_files[0].linked_to_functionality = []
    document.feature_files[0].unlinked = []

    # Act
    markdown = rendered(document)

    # Assert
    assert "Linked to a Functionality" not in markdown
    assert "Unlinked" not in markdown


@pytest.mark.parametrize(("title", "heading"), [("", "# UI test catalog\n"), ("Checkout tests", "# Checkout tests\n")])
def test_the_title_is_the_document_title_input_or_the_default(title, heading):
    # Act
    markdown = rendered(sample(CONTRACT), title)

    # Assert
    assert markdown.startswith(heading)
