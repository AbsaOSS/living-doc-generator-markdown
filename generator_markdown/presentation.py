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
The one presentation module: it maps an input contract model and the view its `document.view` declares to a
presentation model of plain data (what each view shows, the badges, the grouping and the links), which a template only
renders. It filters no record: the input's records are the view's records, and only fields are shown or hidden.

It reads nothing but the `living-doc-utilities` contract models and returns nothing but the dataclasses below, so it
can move into `living-doc-utilities` without a caller seeing a change.
"""

import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Any, Callable, Optional, Sequence, Union

from living_doc_utilities.authoring.url_policy import safe_href
from living_doc_utilities.contracts.codes import ALL_CODES, Emitter
from living_doc_utilities.contracts.common import AcceptanceCriterion, SourceRef
from living_doc_utilities.contracts.coverage_matrix import (
    AcCoverage,
    CoverageMatrixResult,
    CoverageSummary,
    EntityCoverage,
)
from living_doc_utilities.contracts.doc_entities import Entity, PageRef
from living_doc_utilities.contracts.envelope import ContractWarning
from living_doc_utilities.contracts.generator_ready import GeneratorReadyResult
from living_doc_utilities.contracts.ui_test_catalog import (
    CatalogAcLink,
    CatalogScenario,
    FeatureFileCatalog,
    UiTestCatalogResult,
)

INNER = "inner"
RELEASE = "release"

# The title of a document whose input names none and whose run passes no `document-title`.
DEFAULT_TITLES = {
    "technical-project": "Technical project",
    "ui-test-catalog": "UI test catalog",
    "coverage-matrix": "Coverage matrix",
}

# An `Aspect:` criterion's variants, and a coverage breakdown whose row names no keyword, carry this label.
ASPECT_LABEL = "Aspect"

# A Feature's state is derived from its Functionalities; the inner view marks it.
DERIVED_BADGE = "DERIVED"
DEPRECATED_BADGE = "DEPRECATED"

# A scenario's own tag, matched exactly as `ui-tests` holds it, that the test runner skips: such a scenario covers
# nothing, so the coverage matrix counts none of its criteria (`living-doc-utilities` rendering.md § Coverage). The
# catalog marks it, and lists its criteria as linked but not counted, in both views.
SKIP_TAG = "@skip"
SKIPPED_BADGE = "SKIPPED"
COVERS_LABEL = "Covers"
SKIPPED_COVERS_LABEL = "Skipped, not counted"


NOT_LINKED_HEADING = "Not linked to an entity"
TEST_PREFIX = "Test: "
# The inner view marks a test that links no criterion.
NO_AC_BADGE = "NO AC"
# A scenario's `@AC:` tags are its links, which `Covers` shows; the rest are its tags.
AC_TAG_PREFIX = "@AC:"
# An Outline's examples tables open with one of these keyword lines, which the parser reads in English only; their
# rows but the first, the header, are the examples.
_EXAMPLES_RE = re.compile(r"^\s*(?:Examples|Scenarios):")
_TABLE_ROW_RE = re.compile(r"^\s*\|")

# The rendering table's wording for a Feature's `stub_reason`.
STUB_PREFIX = "Surface not yet instrumented"

# A `coverage_pct` of null: the entity, or the matrix, counts no criterion.
NOT_APPLICABLE = "not applicable"

FEATURE = "DocumentedFeature"

_GROUPS = (
    ("DocumentedUserStory", "User Stories"),
    (FEATURE, "Features"),
    ("DocumentedFunctionality", "Functionalities"),
)

# A technical project's overview counts a User Story's or Functionality's criteria by state, in this order; the release
# view holds no `in_review` or `planned` criterion, so it shows only the states it holds.
_STATE_COLUMNS = (
    ("active", "Active"),
    ("in_review", "In review"),
    ("planned", "Planned"),
    ("deprecated", "Deprecated"),
)
_RELEASE_STATES = {"active", "deprecated"}

# A Feature's overview row counts its Functionalities instead.
_FEATURE_COLUMNS = ("Functionalities",)

# The version cell of a planned criterion without a target version.
BACKLOG = "backlog"

# A nested item, as a parser keeps it in its parent's string: `- ` or `-<TAB>` after the line's indent.
_NESTED_ITEM_RE = re.compile(r"^-(?:[ \t]+(?P<text>.*))?$")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")

# The numbers in an entity id, which order the entities of one type; ASCII digits only.
_NUMBER_RE = re.compile(r"[0-9]+")

# A URL with a control character: `urlsplit`, and so `safe_href`, reads it without the character, a renderer with it.
# Or with a lone surrogate, which JSON can carry and no URL can encode.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f\ud800-\udfff]")

SourceDocument = Union[GeneratorReadyResult, UiTestCatalogResult, CoverageMatrixResult]


@dataclass(frozen=True)
class Link:
    """A text that may link: `href` is an absolute URL `safe_href` kept, `anchor` an entity's place in this document.
    With neither, the text shows unlinked."""

    text: str
    href: Optional[str] = None
    anchor: Optional[str] = None


@dataclass(frozen=True)
class OutlineItem:
    """One line of a bullet list: its text and its depth, 0 for an authored item and 1 or more for a nested one."""

    text: str
    depth: int


@dataclass(frozen=True)
class Fact:
    """A labelled one-line value, or a few values shown together."""

    label: str
    values: tuple[Link, ...]


@dataclass(frozen=True)
class Outline:
    """A labelled bullet list, nested items included."""

    label: str
    items: tuple[OutlineItem, ...]


@dataclass(frozen=True)
class Variants:
    """An acceptance criterion's variants: labelled `Aspect`, or with its keyword's name."""

    label: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class NotLoaded:
    """One collector warning, shown as what was not loaded from the input: its code, message and location."""

    code: str
    message: str
    location: tuple[Link, ...]


@dataclass(frozen=True)
class Criterion:
    """One acceptance criterion: its row in its entity's table, then the list fields its note below the table shows."""

    id: str
    version: str
    state: str
    description: str
    variants: tuple[Variants, ...]
    rationale: Optional[str]
    also: tuple[Outline, ...]


@dataclass(frozen=True)
class Page:
    """One PageObject file behind a Feature."""

    route: str
    page_object: str
    primary: bool
    purpose: str
    facts: tuple[Fact, ...]
    notes: tuple[OutlineItem, ...]


@dataclass(frozen=True)
class InnerOnly:
    """What only the inner view shows of an entity; empty in the release view."""

    deprecation: tuple[Fact, ...]
    stub_reason: Optional[str]
    tracker: tuple[Fact, ...]
    not_loaded: tuple[NotLoaded, ...]


@dataclass(frozen=True)
class EntityBody:
    """What both views show of an entity, below its title."""

    paragraphs: tuple[str, ...]
    facts: tuple[Fact, ...]
    outlines: tuple[Outline, ...]
    pages: tuple[Page, ...]
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True)
class EntityView:
    """One User Story, Feature or Functionality."""

    id: str
    anchor: Optional[str]
    title: str
    badges: tuple[str, ...]
    inner: InnerOnly
    body: EntityBody


@dataclass(frozen=True)
class EntityGroup:
    """The entities of one type, in ascending id order."""

    heading: str
    entities: tuple[Any, ...]


@dataclass(frozen=True)
class OverviewRow:
    """One entity in its type's overview table, its counts under the table's columns."""

    id: str
    anchor: Optional[str]
    title: str
    badges: tuple[str, ...]
    counts: tuple[int, ...]


@dataclass(frozen=True)
class OverviewTable:
    """The entities of one type, in ascending id order, with what each counts."""

    heading: str
    columns: tuple[str, ...]
    rows: tuple[OverviewRow, ...]


@dataclass(frozen=True)
class Selection:
    """What the transform's view filter kept, of how many."""

    included_entities: int
    total_entities: int
    included_criteria: int
    total_criteria: int


@dataclass(frozen=True)
class TechnicalProject:
    """A `technical-project` document, from a `generator-ready` input."""

    title: str
    view: str
    version: str
    selection: Selection
    overview: tuple[OverviewTable, ...]
    groups: tuple[EntityGroup, ...]
    not_loaded: tuple[NotLoaded, ...]


@dataclass(frozen=True)
class Covered:
    """A criterion a test links, linked to its entity's chapter, and the one aspect value it covers; none for a bare
    link."""

    link: Link
    aspect: Optional[str]


@dataclass(frozen=True)
class ScenarioMeta:
    """A test's metadata, in the order they show: its status badges, its rule, the criteria it links under their
    label, its examples, its tags but the `@AC:` ones, and its source."""

    badges: tuple[str, ...]
    rule: Optional[str]
    covers_label: str
    covers: tuple[Covered, ...]
    examples: Optional[str]
    tags: tuple[str, ...]
    source: Link


@dataclass(frozen=True)
class ScenarioView:
    """One test's chapter: its heading's name, its metadata and its steps as written. `rule_background` is its rule's
    `Background:`, which shows before the rule's first test only."""

    name: str
    anchor: Optional[str]
    rule_background: tuple[str, ...]
    meta: ScenarioMeta
    steps: tuple[str, ...]


@dataclass(frozen=True)
class CriterionRow:
    """One criterion and one test that links it: the criterion's state badge, none for a criterion no document holds;
    `SKIPPED` for a skipped test; the aspect values the test covers and its tags."""

    ac_id: str
    state: Optional[str]
    test: Link
    skipped: Optional[str]
    aspects: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class TestedEntity:
    """A User Story or Functionality a test links: how many tests do, and a row per criterion and test."""

    id: str
    summary: str
    rows: tuple[CriterionRow, ...]


@dataclass(frozen=True)
class EntityPart:
    """The User Stories, or the Functionalities, that tests link."""

    heading: str
    sentence: str
    entities: tuple[TestedEntity, ...]


@dataclass(frozen=True)
class FeatureFile:
    """One `.feature` file's chapter: its name linked to it, the entities its tests link, its source, its
    `Background:` and its tests."""

    link: Link
    entities_label: str
    entities: tuple[Link, ...]
    source: Link
    background: tuple[str, ...]
    scenarios: tuple[ScenarioView, ...]


@dataclass(frozen=True)
class FilePart:
    """The feature files whose tests link a User Story, or else a Functionality."""

    heading: str
    sentence: str
    files: tuple[FeatureFile, ...]


@dataclass(frozen=True)
class UnlinkedFile:
    """A feature file none of whose tests links a criterion, and how many tests it holds."""

    name: str
    tests: str


@dataclass(frozen=True)
class NotLinked:
    """The inner view's last part: the feature files none of whose tests links a criterion."""

    heading: str
    sentence: str
    files: tuple[UnlinkedFile, ...]


@dataclass(frozen=True)
class ContentsEntry:
    """A part in the table of contents, with its chapters."""

    part: Link
    chapters: tuple[Link, ...]


@dataclass(frozen=True)
class UiTestCatalog:
    """A `ui-test-catalog` document; `home` is its title's anchor, none when the title has none of its own."""

    title: str
    view: str
    home: Optional[str]
    contents: tuple[ContentsEntry, ...]
    entity_parts: tuple[EntityPart, ...]
    file_parts: tuple[FilePart, ...]
    not_linked: Optional[NotLinked]


@dataclass(frozen=True)
class Summary:
    """A coverage summary as its producer wrote it; nothing here is recomputed."""

    coverage: str
    counted: int
    covered: int
    partially_covered: int
    not_covered: int


@dataclass(frozen=True)
class AspectRow:
    """One aspect of a criterion's breakdown."""

    value: str
    status: str
    scenarios: tuple[str, ...]


@dataclass(frozen=True)
class CoverageRow:
    """One counted criterion: its status, `1/3` for a partial one, and its breakdown under its label."""

    ac_id: str
    state: str
    status: str
    fraction: Optional[str]
    scenarios: tuple[str, ...]
    label: Optional[str]
    aspects: tuple[AspectRow, ...]


@dataclass(frozen=True)
class CoverageEntity:
    """One User Story or Functionality and its rows."""

    id: str
    anchor: Optional[str]
    title: str
    badges: tuple[str, ...]
    summary: Summary
    rows: tuple[CoverageRow, ...]


@dataclass(frozen=True)
class PlannedWork:
    """The planned criteria the matrix does not count."""

    total: int
    backlog: int
    by_target_version: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class CoverageMatrix:
    """A `coverage-matrix` document."""

    title: str
    view: str
    summary: Summary
    planned: Optional[PlannedWork]
    groups: tuple[EntityGroup, ...]


@dataclass(frozen=True)
class _CatalogPart:
    """A catalog's part per entity type: the prefix of its ids, its names, and the heading of its tests' part."""

    prefix: str
    singular: str
    plural: str
    tests: str


_CATALOG_PARTS = (
    _CatalogPart("US-", "User Story", "User Stories", "User Story tests"),
    _CatalogPart("FUNC-", "Functionality", "Functionalities", "Functionality tests"),
)


Presentation = Union[TechnicalProject, UiTestCatalog, CoverageMatrix]


def present(document: SourceDocument, title: str = "") -> Presentation:
    """
    Map an input to what its declared view shows.

    @param document: A `generator-ready`, `ui-test-catalog` or `coverage-matrix` model.
    @param title: The document's title; when empty, the input's own title, then the document type's default.
    @return: The presentation model the templates render.
    """
    if isinstance(document, GeneratorReadyResult):
        return _technical_project(document, title)
    if isinstance(document, UiTestCatalogResult):
        return _ui_test_catalog(document, title)
    return _coverage_matrix(document, title)


def render_manifest(presentation: Presentation) -> dict[str, Any]:
    """
    What a presentation renders, for a run report: the entity ids, criteria, aspects, badges, scenarios and what was
    not loaded, under the view.

    @param presentation: The model a document was rendered from.
    @return: Plain JSON-ready data, in document order.
    """
    if isinstance(presentation, TechnicalProject):
        return _technical_project_manifest(presentation)
    if isinstance(presentation, UiTestCatalog):
        return _ui_test_catalog_manifest(presentation)
    return _coverage_matrix_manifest(presentation)


# ---------------------------------------------------------------------------
# technical-project
# ---------------------------------------------------------------------------


def _technical_project(document: GeneratorReadyResult, title: str) -> TechnicalProject:
    view = document.document.view
    entities = document.content.entities
    held = {entity.entity_id for entity in entities}
    anchors = _anchors(held)
    shown = _not_loaded_warnings(document.warnings) if view == INNER else []
    under = {
        entity_id: tuple(_not_loaded(warning) for warning in shown if warning.entity_id == entity_id)
        for entity_id in held
    }
    selection = document.document.selection_summary
    return TechnicalProject(
        title=title or document.document.title or DEFAULT_TITLES["technical-project"],
        view=view,
        version=document.document.version,
        selection=Selection(
            included_entities=selection.included_entities,
            total_entities=selection.total_entities,
            included_criteria=selection.included_acceptance_criteria,
            total_criteria=selection.total_acceptance_criteria,
        ),
        overview=_overview(entities, view, anchors),
        groups=_groups(
            entities,
            lambda entity: _entity_view(entity, view, anchors, under[entity.entity_id]),
            lambda entity: entity.type,
        ),
        not_loaded=tuple(_not_loaded(warning) for warning in shown if warning.entity_id not in held),
    )


def _groups(
    records: Sequence[Any], build: Callable[[Any], Any], type_of: Callable[[Any], str]
) -> tuple[EntityGroup, ...]:
    """Records grouped by entity type in the canon's order, each group in ascending id order; an empty group is left
    out."""
    return tuple(
        EntityGroup(heading=heading, entities=members) for _, heading, members in _by_type(records, build, type_of)
    )


def _by_type(
    records: Sequence[Any], build: Callable[[Any], Any], type_of: Callable[[Any], str]
) -> list[tuple[str, str, tuple[Any, ...]]]:
    """Each entity type's built records, with the type and its heading: the types in the canon's order, each type's
    records in ascending id order, a type without one left out."""
    grouped = []
    for doc_type, heading in _GROUPS:
        members = sorted((build(record) for record in records if type_of(record) == doc_type), key=_id_order)
        if members:
            grouped.append((doc_type, heading, tuple(members)))
    return grouped


def _overview(entities: list[Entity], view: str, anchors: dict[str, str]) -> tuple[OverviewTable, ...]:
    """
    One table per entity type, in the chapters' order: a User Story's or Functionality's criteria by state, only the
    states the view holds, and a Feature's Functionalities. Counted from the input, never from coverage.
    """
    states = tuple(column for column in _STATE_COLUMNS if view == INNER or column[0] in _RELEASE_STATES)
    tables = []
    for doc_type, heading, rows in _by_type(
        entities, lambda entity: _overview_row(entity, view, anchors, states), lambda entity: entity.type
    ):
        columns = _FEATURE_COLUMNS if doc_type == FEATURE else tuple(label for _, label in states)
        tables.append(OverviewTable(heading=heading, columns=columns, rows=rows))
    return tuple(tables)


def _overview_row(
    entity: Entity, view: str, anchors: dict[str, str], states: tuple[tuple[str, str], ...]
) -> OverviewRow:
    """A Feature's count is of the Functionalities its chapter lists, the ones the document does not hold included."""
    if entity.type == FEATURE:
        counts: tuple[int, ...] = (len([target for target in entity.functionalities if target]),)
    else:
        held: Counter[str] = Counter(criterion.state for criterion in entity.acceptance_criteria)
        counts = tuple(held[state] for state, _ in states)
    return OverviewRow(
        id=entity.entity_id,
        anchor=anchors.get(entity.entity_id),
        title=entity.title,
        badges=_entity_badges(entity, view),
        counts=counts,
    )


def _id_order(entity: Union[EntityView, CoverageEntity, OverviewRow]) -> tuple[bool, tuple[tuple[int, str], ...]]:
    """
    An entity's place among its type's: by the numbers in its id, number by number and each by its value, so `US-2`
    comes before `US-10` and `FEAT-2024-3` before `FEAT-2024-10`; an id without a number after them. The sort is
    stable, so ids of equal numbers keep their input order.
    """
    # Each number as its digits without leading zeros, compared by length, then digit by digit, as `int()` would
    # compare them: `int()` itself refuses a run of more than 4300 digits.
    return _number_order(entity.id)


def _number_order(text: str) -> tuple[bool, tuple[tuple[int, str], ...]]:
    """`_id_order` of an id as text: an entity's, or an acceptance criterion's."""
    numbers = tuple((len(digits), digits) for digits in (run.lstrip("0") for run in _NUMBER_RE.findall(text)))
    return (not numbers, numbers)


def _entity_view(entity: Entity, view: str, anchors: dict[str, str], not_loaded: tuple[NotLoaded, ...]) -> EntityView:
    return EntityView(
        id=entity.entity_id,
        anchor=anchors.get(entity.entity_id),
        title=entity.title,
        badges=_entity_badges(entity, view),
        inner=_inner_only(entity, not_loaded) if view == INNER else InnerOnly((), None, (), ()),
        body=EntityBody(
            paragraphs=_paragraphs(entity.narrative) + _paragraphs(entity.purpose),
            facts=_entity_facts(entity, anchors),
            outlines=_present_outlines(
                ("Business value", entity.business_value),
                ("Preconditions", entity.preconditions),
                ("Not in scope", entity.not_in_scope),
                ("Notes", entity.notes),
            ),
            pages=tuple(_page(page, anchors) for page in entity.pages),
            criteria=tuple(_criterion(criterion) for criterion in entity.acceptance_criteria),
        ),
    )


def _inner_only(entity: Entity, not_loaded: tuple[NotLoaded, ...]) -> InnerOnly:
    """The deprecation date and reason, the stub reason, the tracker paths and what was not loaded."""
    return InnerOnly(
        deprecation=_deprecation(entity),
        stub_reason=_stub_text(entity.stub_reason) if entity.stub_reason else None,
        tracker=_tracker(entity),
        not_loaded=not_loaded,
    )


def _entity_badges(entity: Entity, view: str) -> tuple[str, ...]:
    """A User Story's or Functionality's state in both views; a Feature's derived one marked in inner, and in release
    only a `DEPRECATED` badge, when it is deprecated."""
    if entity.state_origin != "derived":
        return (_badge(entity.state),)
    if view == INNER:
        return (_badge(entity.state), DERIVED_BADGE)
    return (DEPRECATED_BADGE,) if entity.state == "deprecated" else ()


def _badge(state: str) -> str:
    return state.replace("_", " ").upper()


def _deprecation(entity: Entity) -> tuple[Fact, ...]:
    facts = []
    if entity.deprecated_at:
        facts.append(_fact("Deprecated on", [entity.deprecated_at]))
    if entity.deprecation_reason:
        facts.append(_fact("Deprecation reason", [entity.deprecation_reason]))
    return tuple(facts)


def _stub_text(stub_reason: str) -> str:
    """The rendering table's "surface not yet instrumented: …", the authored reason after it as written."""
    return f"{STUB_PREFIX}: {stub_reason}"


def _entity_facts(entity: Entity, anchors: dict[str, str]) -> tuple[Fact, ...]:
    """Every one-line field an entity carries, in a fixed order; an empty field is left out."""
    facts = [
        Fact(label="Source", values=(_source_link(entity.source_ref),)),
        _fact("Linked issue", [entity.source], link=True),
        _fact("Tags", entity.tags),
        _fact("Surface", [entity.surface_type]),
        _fact("Type", [entity.func_type]),
        _fact("Owners", entity.owners),
        _relation("Parent", [entity.parent], anchors),
        _relation("User stories", entity.user_stories, anchors),
        _relation("Functionalities", entity.functionalities, anchors),
        _relation("Feature dependencies", entity.feature_dependencies, anchors),
        _fact("External dependencies", entity.external_dependencies),
        _fact("Wizard steps", entity.wizard_steps),
        _relation("Superseded by", [entity.superseded_by], anchors),
        _fact("Rationale", [entity.rationale]),
    ]
    return tuple(fact for fact in facts if fact.values)


def _source_link(ref: SourceRef) -> Link:
    """The record's place in its tracker or repository, named by system and native id."""
    return _url_link(f"{ref.system} {ref.native_id}", ref.url)


def _tracker(entity: Entity) -> tuple[Fact, ...]:
    """Azure DevOps' area and iteration path, which only the inner view shows."""
    ref = entity.source_ref
    facts = (_fact("Area", [ref.area_path]), _fact("Iteration", [ref.iteration_path]))
    return tuple(fact for fact in facts if fact.values)


def _page(page: PageRef, anchors: dict[str, str]) -> Page:
    facts = (_fact("Owners", page.owners), _relation("Functionalities", page.functionalities, anchors))
    return Page(
        route=page.route,
        page_object=page.page_object,
        primary=page.is_primary,
        purpose=page.purpose,
        facts=tuple(fact for fact in facts if fact.values),
        notes=_outline(page.notes),
    )


def _criterion(criterion: AcceptanceCriterion) -> Criterion:
    """A criterion's row: `v<version>`, or the backlog for a planned one without a version; its state as stored, and a
    deprecated one's removal target."""
    return Criterion(
        id=criterion.id,
        version=f"v{criterion.version}" if criterion.version else BACKLOG,
        state=(
            f"{criterion.state}, removal planned v{criterion.removal_planned}"
            if criterion.removal_planned
            else criterion.state
        ),
        description=" ".join(criterion.description.split()),
        variants=_variants(criterion),
        rationale=criterion.rationale or None,
        also=_present_outlines(
            ("Also requires", criterion.preconditions), ("Also not in scope", criterion.not_in_scope)
        ),
    )


def _variants(criterion: AcceptanceCriterion) -> tuple[Variants, ...]:
    """A keyword criterion's variants under its keyword's name; `aspect` under `Aspect` unless a keyword holds them.
    The name shows as stored (`payment_field`): the parser folds the authored spelling, so no other can be shown."""
    variants = [Variants(label=name, values=tuple(values)) for name, values in criterion.placeholder_values.items()]
    if criterion.aspect and all(list(variant.values) != criterion.aspect for variant in variants):
        variants.insert(0, Variants(label=ASPECT_LABEL, values=tuple(criterion.aspect)))
    return tuple(variants)


# ---------------------------------------------------------------------------
# What was not loaded
# ---------------------------------------------------------------------------


def _not_loaded_warnings(warnings: list[ContractWarning]) -> list[ContractWarning]:
    """The warnings a collector emitted; a transform's or the toolkit's own are not what was not loaded."""
    return [
        warning
        for warning in warnings
        if warning.code in ALL_CODES and ALL_CODES[warning.code].emitter is Emitter.COLLECTOR
    ]


def _not_loaded(warning: ContractWarning) -> NotLoaded:
    """A warning's code, message and location: its file, and its line linked as `source_url#L<line_no>`. Never its
    `context`, `entity_id` or `ac_id`."""
    location = []
    line = f"line {warning.line_no}" if warning.line_no is not None else None
    if warning.path:
        file_href = warning.source_url if line is None else None
        location.append(_url_link(warning.path, file_href))
    if line is not None:
        line_href = f"{warning.source_url}#L{warning.line_no}" if warning.source_url else None
        location.append(_url_link(line, line_href))
    elif not warning.path and warning.source_url:
        location.append(_url_link("source", warning.source_url))
    return NotLoaded(code=warning.code, message=warning.message, location=tuple(location))


# ---------------------------------------------------------------------------
# ui-test-catalog
# ---------------------------------------------------------------------------


def _ui_test_catalog(document: UiTestCatalogResult, title: str) -> UiTestCatalog:
    """
    The entities that tests link, then the tests by feature file, as AbsaOSS/living-doc#155 agreed. Everything is
    decided from the links the input holds, after a release view's drop: a file none of whose tests holds a link is in
    no chapter, and only the inner view lists it.
    """
    view = document.document.view
    title = title or DEFAULT_TITLES["ui-test-catalog"]
    names = _file_names([catalog.feature_file for catalog in document.feature_files])
    parts, unlinked = _catalog_files(document, view)
    tests = _named_tests([catalog for _, part_files in parts for catalog in part_files])
    entities = _linked_entities(tests)
    headings = [title] + ([NOT_LINKED_HEADING] if unlinked else []) + [TEST_PREFIX + name for _, _, name in tests]
    headings += [
        heading for part in _CATALOG_PARTS for heading in ([part.plural, *entities[part]] if entities[part] else [])
    ]
    headings += [
        heading
        for part, part_files in parts
        for heading in ([part.tests, *(names[catalog.feature_file] for catalog in part_files)] if part_files else [])
    ]
    anchors = _heading_anchors(headings)

    views = {
        _test_key(catalog, scenario): _scenario(scenario, name, view, anchors, names[catalog.feature_file])
        for catalog, scenario, name in tests
    }
    entity_parts = tuple(
        EntityPart(
            heading=part.plural,
            sentence=f"{_count(len(entities[part]), part.singular, part.plural)}: each tested criterion with its "
            "state and the tests that cover it.",
            entities=tuple(_tested_entity(entity_id, tests, views) for entity_id in entities[part]),
        )
        for part in _CATALOG_PARTS
        if entities[part]
    )
    file_parts = tuple(
        FilePart(
            heading=part.tests,
            sentence=f"{_count(len(part_files), 'feature file')}, "
            f"{_count(sum(len(_file_scenarios(catalog)) for catalog in part_files), 'test')}, each with its metadata "
            "and steps.",
            files=tuple(_feature_file(catalog, names, anchors, views) for catalog in part_files),
        )
        for part, part_files in parts
        if part_files
    )
    not_linked = _not_linked(unlinked, names)
    return UiTestCatalog(
        title=title,
        view=view,
        home=anchors.get(title),
        contents=_contents(entity_parts, file_parts, not_linked, anchors),
        entity_parts=entity_parts,
        file_parts=file_parts,
        not_linked=not_linked,
    )


def _not_linked(
    unlinked: list[tuple[FeatureFileCatalog, list[CatalogScenario]]], names: dict[str, str]
) -> Optional[NotLinked]:
    """The inner view's files none of whose tests links a criterion, each with its test count; none without one."""
    if not unlinked:
        return None
    return NotLinked(
        heading=NOT_LINKED_HEADING,
        sentence=f"{_count(len(unlinked), 'feature file')} whose tests link no criterion.",
        files=tuple(
            UnlinkedFile(name=names[catalog.feature_file], tests=_count(len(scenarios), "test"))
            for catalog, scenarios in unlinked
        ),
    )


def _catalog_files(
    document: UiTestCatalogResult, view: str
) -> tuple[list[tuple[_CatalogPart, list[FeatureFileCatalog]]], list[tuple[FeatureFileCatalog, list[CatalogScenario]]]]:
    """The files with a chapter, by part and in file-name order; and, in the inner view, the files without one."""
    files = [(catalog, _file_scenarios(catalog)) for catalog in document.feature_files]
    parts = [
        (
            part,
            sorted(
                (catalog for catalog, scenarios in files if _holds_a_link(scenarios) and _file_part(scenarios) is part),
                key=lambda catalog: _file_name_order(catalog.feature_file),
            ),
        )
        for part in _CATALOG_PARTS
    ]
    unlinked = sorted(
        ((catalog, scenarios) for catalog, scenarios in files if view == INNER and not _holds_a_link(scenarios)),
        key=lambda item: _file_name_order(item[0].feature_file),
    )
    return parts, unlinked


def _linked_entities(
    tests: list[tuple[FeatureFileCatalog, CatalogScenario, str]],
) -> dict[_CatalogPart, list[str]]:
    """Per part, the entities the tests' links name, in ascending id order."""
    linked = {_entity_of(link.id) for _, scenario, _ in tests for link in scenario.acceptance_criteria}
    return {
        part: sorted((entity_id for entity_id in linked if entity_id.startswith(part.prefix)), key=_number_order)
        for part in _CATALOG_PARTS
    }


def _named_tests(catalogs: list[FeatureFileCatalog]) -> list[tuple[FeatureFileCatalog, CatalogScenario, str]]:
    """Every rendered test in document order, with its heading's name."""
    tests = [(catalog, scenario) for catalog in catalogs for scenario in _file_scenarios(catalog)]
    repeated = Counter(_title_key(scenario.title) for _, scenario in tests)
    return [
        (catalog, scenario, _test_name(scenario.title, catalog.feature_file, repeated)) for catalog, scenario in tests
    ]


def _file_scenarios(catalog: FeatureFileCatalog) -> list[CatalogScenario]:
    """A file's tests once each, as its groups list them, in the order of their lines; a test without one after."""
    groups = catalog.linked_to_user_story + catalog.linked_to_functionality
    found = [scenario for group in groups for scenario in group.scenarios] + catalog.unlinked
    once: dict[str, CatalogScenario] = {}
    for scenario in found:
        once.setdefault(scenario.scenario_id, scenario)
    return sorted(once.values(), key=lambda scenario: (scenario.line is None, scenario.line or 0))


def _test_key(catalog: FeatureFileCatalog, scenario: CatalogScenario) -> tuple[str, str]:
    return (catalog.feature_file, scenario.scenario_id)


def _holds_a_link(scenarios: list[CatalogScenario]) -> bool:
    return any(scenario.acceptance_criteria for scenario in scenarios)


def _file_part(scenarios: list[CatalogScenario]) -> _CatalogPart:
    """A file's part: the User Story tests when a test links a User Story, else the Functionality tests."""
    user_stories, functionalities = _CATALOG_PARTS
    links = [link for scenario in scenarios for link in scenario.acceptance_criteria]
    return user_stories if any(link.id.startswith(user_stories.prefix) for link in links) else functionalities


def _file_name_order(feature_file: str) -> tuple[str, str]:
    return (PurePosixPath(feature_file).name, feature_file)


def _file_names(feature_files: list[str]) -> dict[str, str]:
    """Each file's heading: its name, or its path when another file has the same name."""
    shared = Counter(PurePosixPath(feature_file).name for feature_file in set(feature_files))
    return {
        feature_file: feature_file if shared[PurePosixPath(feature_file).name] > 1 else PurePosixPath(feature_file).name
        for feature_file in feature_files
    }


def _title_key(title: str) -> str:
    """What makes two test titles one heading: the same anchor, or the same text for a title without one."""
    return anchor(TEST_PREFIX + title) or " ".join(title.split())


def _test_name(title: str, feature_file: str, repeated: Counter[str]) -> str:
    """A test's title, with its file's name when another rendered test has the same title."""
    if repeated[_title_key(title)] > 1:
        return f"{title} ({PurePosixPath(feature_file).stem})"
    return title


def _entity_of(ac_id: str) -> str:
    """The entity an acceptance criterion belongs to: its id without the criterion's number."""
    return ac_id.rsplit("-", 1)[0]


def _heading_anchors(headings: list[str]) -> dict[str, str]:
    """The headings a link can point at, with their anchors: a heading without one, or sharing it, is left out, as a
    renderer would number the second heading's."""
    found = {heading: anchor(heading) for heading in headings}
    shared = Counter(anchor(heading) for heading in headings)
    return {heading: place for heading, place in found.items() if place is not None and shared[place] == 1}


def _count(number: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{number} {singular if number == 1 else plural or singular + 's'}"


def _scenario(scenario: CatalogScenario, name: str, view: str, anchors: dict[str, str], file_name: str) -> ScenarioView:
    skipped = SKIP_TAG in scenario.tags
    badges = ((SKIPPED_BADGE,) if skipped else ()) + (
        (NO_AC_BADGE,) if view == INNER and not scenario.acceptance_criteria else ()
    )
    return ScenarioView(
        name=name,
        anchor=anchors.get(TEST_PREFIX + name),
        rule_background=(),
        meta=ScenarioMeta(
            badges=badges,
            rule=scenario.rule,
            covers_label=SKIPPED_COVERS_LABEL if skipped else COVERS_LABEL,
            covers=tuple(
                Covered(link=Link(text=link.id, anchor=anchors.get(_entity_of(link.id))), aspect=link.aspect)
                for link in scenario.acceptance_criteria
            ),
            examples=_examples(scenario.steps),
            tags=_shown_tags(scenario),
            source=_scenario_source(scenario, file_name),
        ),
        steps=tuple(scenario.steps),
    )


def _shown_tags(scenario: CatalogScenario) -> tuple[str, ...]:
    """A test's tags but its `@AC:` links, which `Covers` shows."""
    return tuple(tag for tag in scenario.tags if not tag.startswith(AC_TAG_PREFIX))


def _scenario_source(scenario: CatalogScenario, file_name: str) -> Link:
    """The test's line in its file, `#L<line>` after the file's URL, when it has a line and the URL no fragment."""
    url = scenario.source_ref.url
    if scenario.line is not None and "#" not in url:
        return _url_link(f"{file_name}#L{scenario.line}", f"{url}#L{scenario.line}")
    return _url_link(file_name, url)


def _examples(steps: list[str]) -> Optional[str]:
    """An Outline's examples: the rows of each `Examples:` table but its header; none without an `Examples:` line."""
    rows: Optional[int] = None
    header = in_examples = False
    for line in steps:
        if _EXAMPLES_RE.match(line):
            rows, header, in_examples = rows or 0, True, True
        elif in_examples and _TABLE_ROW_RE.match(line):
            rows = (rows or 0) + (0 if header else 1)
            header = False
        else:
            in_examples = False
    return None if rows is None else _count(rows, "example")


def _feature_file(
    catalog: FeatureFileCatalog,
    names: dict[str, str],
    anchors: dict[str, str],
    views: dict[tuple[str, str], ScenarioView],
) -> FeatureFile:
    scenarios = _file_scenarios(catalog)
    held = {_entity_of(link.id) for scenario in scenarios for link in scenario.acceptance_criteria}
    entities = [
        entity_id
        for part in _CATALOG_PARTS
        for entity_id in sorted((e for e in held if e.startswith(part.prefix)), key=_number_order)
    ]
    shown: list[ScenarioView] = []
    rules: set[str] = set()
    for scenario in scenarios:
        chapter = views[_test_key(catalog, scenario)]
        if scenario.rule is not None and scenario.rule not in rules:
            rules.add(scenario.rule)
            chapter = replace(chapter, rule_background=tuple(scenario.rule_background))
        shown.append(chapter)
    name = names[catalog.feature_file]
    return FeatureFile(
        link=Link(text=name, anchor=anchors.get(name)),
        entities_label="Entity" if len(entities) == 1 else "Entities",
        entities=tuple(Link(text=entity_id, anchor=anchors.get(entity_id)) for entity_id in entities),
        source=_url_link(name, scenarios[0].source_ref.url.split("#", 1)[0]),
        background=tuple(catalog.background),
        scenarios=tuple(shown),
    )


def _tested_entity(
    entity_id: str,
    tests: list[tuple[FeatureFileCatalog, CatalogScenario, str]],
    views: dict[tuple[str, str], ScenarioView],
) -> TestedEntity:
    """A row per criterion and test, by criterion, then in the tests' order."""
    pairs: dict[tuple[str, tuple[str, str]], list[CatalogAcLink]] = {}
    for catalog, scenario, _ in tests:
        for link in scenario.acceptance_criteria:
            if _entity_of(link.id) == entity_id:
                pairs.setdefault((link.id, _test_key(catalog, scenario)), []).append(link)
    rows = []
    for (ac_id, key), links in sorted(pairs.items(), key=lambda pair: _number_order(pair[0][0])):
        chapter = views[key]
        rows.append(
            CriterionRow(
                ac_id=ac_id,
                state=_badge(links[0].state) if links[0].state else None,
                test=Link(text=chapter.name, anchor=chapter.anchor),
                skipped=SKIPPED_BADGE if SKIPPED_BADGE in chapter.meta.badges else None,
                aspects=tuple(_unique([link.aspect for link in links if link.aspect])),
                tags=chapter.meta.tags,
            )
        )
    tested = list(dict.fromkeys(key for _, key in pairs))
    skipped = [key for key in tested if SKIPPED_BADGE in views[key].meta.badges]
    summary = _count(len(tested), "test") + (f", {len(skipped)} skipped" if skipped else "") + "."
    return TestedEntity(id=entity_id, summary=summary, rows=tuple(rows))


def _contents(
    entity_parts: tuple[EntityPart, ...],
    file_parts: tuple[FilePart, ...],
    not_linked: Optional[NotLinked],
    anchors: dict[str, str],
) -> tuple[ContentsEntry, ...]:
    """The parts in their order, each with its chapters: every entity and every feature file."""
    entries = [
        ContentsEntry(
            part=Link(text=part.heading, anchor=anchors.get(part.heading)),
            chapters=tuple(Link(text=entity.id, anchor=anchors.get(entity.id)) for entity in part.entities),
        )
        for part in entity_parts
    ]
    entries += [
        ContentsEntry(
            part=Link(text=file_part.heading, anchor=anchors.get(file_part.heading)),
            chapters=tuple(file.link for file in file_part.files),
        )
        for file_part in file_parts
    ]
    if not_linked is not None:
        entries.append(
            ContentsEntry(part=Link(text=not_linked.heading, anchor=anchors.get(not_linked.heading)), chapters=())
        )
    return tuple(entries)


# ---------------------------------------------------------------------------
# coverage-matrix
# ---------------------------------------------------------------------------


def _coverage_matrix(document: CoverageMatrixResult, title: str) -> CoverageMatrix:
    view = document.document.view
    planned = document.planned_summary
    anchors = _anchors({entity.entity_id for entity in document.entities})
    return CoverageMatrix(
        title=title or DEFAULT_TITLES["coverage-matrix"],
        view=view,
        summary=_summary(document.summary),
        planned=(
            PlannedWork(
                total=planned.total,
                backlog=planned.backlog,
                by_target_version=tuple(planned.by_target_version.items()),
            )
            if view == INNER
            else None
        ),
        groups=_groups(document.entities, lambda entity: _coverage_entity(entity, anchors), lambda entity: entity.type),
    )


def _coverage_entity(entity: EntityCoverage, anchors: dict[str, str]) -> CoverageEntity:
    return CoverageEntity(
        id=entity.entity_id,
        anchor=anchors.get(entity.entity_id),
        title=entity.title,
        badges=(_badge(entity.state),),
        summary=_summary(entity.summary),
        rows=tuple(_coverage_row(row) for row in entity.acceptance_criteria),
    )


def _summary(summary: CoverageSummary) -> Summary:
    """The summary's own figures: a generator reads them and never computes one."""
    return Summary(
        coverage=NOT_APPLICABLE if summary.coverage_pct is None else f"{summary.coverage_pct:.1f}%",
        counted=summary.counted_acs,
        covered=summary.covered_acs,
        partially_covered=summary.partially_covered_acs,
        not_covered=summary.not_covered_acs,
    )


def _coverage_row(row: AcCoverage) -> CoverageRow:
    """A row's status; a partial one shows its covered and declared aspects before the breakdown, which is labelled
    with the row's `keyword`, or `Aspect` when it has none."""
    partial = row.status == "partially_covered"
    return CoverageRow(
        ac_id=row.ac_id,
        state=row.state,
        status=_badge(row.status),
        fraction=f"{row.covered_aspects()}/{len(row.aspects)}" if partial else None,
        scenarios=tuple(row.scenario_ids),
        label=(row.keyword or ASPECT_LABEL) if row.aspects else None,
        aspects=tuple(
            AspectRow(value=aspect.aspect, status=aspect.status.replace("_", " "), scenarios=tuple(aspect.scenario_ids))
            for aspect in row.aspects
        ),
    )


# ---------------------------------------------------------------------------
# Render manifests
# ---------------------------------------------------------------------------


def _technical_project_manifest(presentation: TechnicalProject) -> dict[str, Any]:
    entities = [entity for group in presentation.groups for entity in group.entities]
    criteria = [criterion for entity in entities for criterion in entity.body.criteria]
    return {
        "view": presentation.view,
        "entities": [entity.id for entity in entities],
        "acceptance_criteria": [criterion.id for criterion in criteria],
        "aspects": [
            {"ac_id": criterion.id, "label": variant.label, "values": list(variant.values)}
            for criterion in criteria
            for variant in criterion.variants
        ],
        "badges": [{"id": entity.id, "badges": list(entity.badges)} for entity in entities if entity.badges],
        "scenarios": [],
        "not_loaded": [
            {"code": item.code, "under": entity.id} for entity in entities for item in entity.inner.not_loaded
        ]
        + [{"code": item.code, "under": None} for item in presentation.not_loaded],
    }


def _ui_test_catalog_manifest(presentation: UiTestCatalog) -> dict[str, Any]:
    rows = [row for part in presentation.entity_parts for entity in part.entities for row in entity.rows]
    tests = [scenario for part in presentation.file_parts for file in part.files for scenario in file.scenarios]
    aspects: dict[str, list[str]] = {}
    states: dict[str, str] = {}
    for row in rows:
        aspects.setdefault(row.ac_id, [])
        aspects[row.ac_id] += [value for value in row.aspects if value not in aspects[row.ac_id]]
        if row.state is not None:
            states.setdefault(row.ac_id, row.state)
    return {
        "view": presentation.view,
        "entities": [entity.id for part in presentation.entity_parts for entity in part.entities],
        "acceptance_criteria": list(aspects),
        "aspects": [{"ac_id": ac_id, "label": None, "values": values} for ac_id, values in aspects.items() if values],
        "badges": [{"id": ac_id, "badges": [state]} for ac_id, state in states.items()]
        + [{"id": test.name, "badges": list(test.meta.badges)} for test in tests if test.meta.badges],
        "scenarios": [test.name for test in tests],
        "not_loaded": [],
    }


def _coverage_matrix_manifest(presentation: CoverageMatrix) -> dict[str, Any]:
    entities = [entity for group in presentation.groups for entity in group.entities]
    rows = [row for entity in entities for row in entity.rows]
    return {
        "view": presentation.view,
        "entities": [entity.id for entity in entities],
        "acceptance_criteria": [row.ac_id for row in rows],
        "aspects": [
            {"ac_id": row.ac_id, "label": row.label, "values": [aspect.value for aspect in row.aspects]}
            for row in rows
            if row.aspects
        ],
        "badges": [{"id": entity.id, "badges": list(entity.badges)} for entity in entities]
        + [{"id": row.ac_id, "badges": [row.status]} for row in rows],
        "scenarios": _unique(
            [scenario for row in rows for scenario in row.scenarios]
            + [scenario for row in rows for aspect in row.aspects for scenario in aspect.scenarios]
        ),
        "not_loaded": [],
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def anchor(entity_id: str) -> Optional[str]:
    """
    An entity's place in its document: the anchor every renderer derives from a heading that holds the id alone, as
    printed, its runs of white space one space. None for an id outside ASCII, whose anchor renderers derive
    differently, or one whose anchor would be empty.
    """
    if not entity_id.isascii():
        return None
    return re.sub(r"[^a-z0-9_ -]", "", " ".join(entity_id.split()).lower()).replace(" ", "-") or None


def _anchors(entity_ids: set[str]) -> dict[str, str]:
    """The ids a link can point at, with their anchors: an id without one, or sharing it, is left out, as a renderer
    would number the second heading's."""
    found = {entity_id: anchor(entity_id) for entity_id in entity_ids}
    shared = Counter(found.values())
    return {entity_id: place for entity_id, place in found.items() if place is not None and shared[place] == 1}


def _url_link(text: str, url: Optional[str]) -> Link:
    """`text` linked to `url` only when `safe_href` keeps it as written; a rejected link shows as its text."""
    return Link(text=text, href=_kept_href(url) if url else None)


def _kept_href(url: str) -> Optional[str]:
    """`url` when `safe_href` keeps it and a renderer reads it as `safe_href` did; otherwise None."""
    if url != url.strip() or _CONTROL_RE.search(url):
        # `urlsplit` strips them before `safe_href` looks: ` javascript:x` is checked as `javascript:x`, but a
        # renderer writes it as the relative `%20javascript:x`.
        return None
    try:
        return safe_href(url)
    except ValueError:
        # `urlsplit` cannot read the host, as in `https://[TODO]/issue/42`.
        return None


def _fact(label: str, values: Sequence[Optional[str]], link: bool = False) -> Fact:
    """A fact of the values that are set; `link` links each one `safe_href` keeps, and shows the rest as text."""
    return Fact(label=label, values=tuple(_url_link(v, v) if link else Link(text=v) for v in values if v))


def _relation(label: str, targets: Sequence[Optional[str]], anchors: dict[str, str]) -> Fact:
    """Entity ids linked to their place in this document; an id the document does not hold, or that has no anchor of
    its own, shows as text."""
    return Fact(label=label, values=tuple(Link(text=t, anchor=anchors.get(t)) for t in targets if t))


def _paragraphs(text: Optional[str]) -> tuple[str, ...]:
    """A text's paragraphs, each on one line, as a renderer joins a paragraph's lines."""
    if not text or not text.strip():
        return ()
    return tuple(" ".join(part.split()) for part in _BLANK_LINE_RE.split(text.strip()) if part.strip())


def _present_outlines(*fields: tuple[str, list[str]]) -> tuple[Outline, ...]:
    return tuple(Outline(label=label, items=_outline(entries)) for label, entries in fields if entries)


def _outline(entries: list[str]) -> tuple[OutlineItem, ...]:
    """A bullet-list field's items, each nested item (`"Parent.\\n  - Child."`) a deeper item of its own; a line
    without `- ` continues the item above it."""
    items: list[OutlineItem] = []
    for entry in entries:
        head, *rest = entry.split("\n")
        items.append(OutlineItem(text=" ".join(head.split()), depth=0))
        open_indents: list[int] = []
        for line in rest:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            nested = _NESTED_ITEM_RE.match(line.strip())
            if nested is None:
                last = items[-1]
                items[-1] = OutlineItem(text=" ".join(f"{last.text} {line}".split()), depth=last.depth)
                continue
            while open_indents and open_indents[-1] >= indent:
                open_indents.pop()
            open_indents.append(indent)
            items.append(OutlineItem(text=" ".join((nested.group("text") or "").split()), depth=len(open_indents)))
    return tuple(items)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
