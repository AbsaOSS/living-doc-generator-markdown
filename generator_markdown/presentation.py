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
from dataclasses import dataclass
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
from living_doc_utilities.contracts.ui_test_catalog import LinkedScenarios, UiTestCatalogResult
from living_doc_utilities.contracts.ui_tests import Scenario

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

# The rendering table's wording for a Feature's `stub_reason`.
STUB_PREFIX = "Surface not yet instrumented"

# A `coverage_pct` of null: the entity, or the matrix, counts no criterion.
NOT_APPLICABLE = "not applicable"

_GROUPS = (
    ("DocumentedUserStory", "User Stories"),
    ("DocumentedFeature", "Features"),
    ("DocumentedFunctionality", "Functionalities"),
)

# A nested item, as a parser keeps it in its parent's string: `- ` after the line's indent.
_NESTED_ITEM_RE = re.compile(r"^-(?: +(?P<text>.*))?$")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")

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
    """One acceptance criterion under its entity."""

    id: str
    header: str
    description: str
    lifecycle: Optional[str]
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
    anchor: str
    title: str
    badges: tuple[str, ...]
    inner: InnerOnly
    body: EntityBody


@dataclass(frozen=True)
class EntityGroup:
    """The entities of one type, in input order."""

    heading: str
    entities: tuple[Any, ...]


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
    groups: tuple[EntityGroup, ...]
    not_loaded: tuple[NotLoaded, ...]


@dataclass(frozen=True)
class Covered:
    """A criterion a scenario links to, and the one aspect value it covers; none for a bare link."""

    ac_id: str
    aspect: Optional[str]


@dataclass(frozen=True)
class ScenarioView:
    """One Gherkin scenario: its tags, the criteria it covers and a link to its source."""

    id: str
    title: str
    tags: tuple[str, ...]
    covers: tuple[Covered, ...]
    source: Link


@dataclass(frozen=True)
class LinkedGroup:
    """The scenarios one file links to one entity."""

    entity_id: str
    scenarios: tuple[ScenarioView, ...]


@dataclass(frozen=True)
class FeatureFile:
    """One `.feature` file's scenarios: linked to a User Story, linked to a Functionality, unlinked."""

    name: str
    user_stories: tuple[LinkedGroup, ...]
    functionalities: tuple[LinkedGroup, ...]
    unlinked: tuple[ScenarioView, ...]


@dataclass(frozen=True)
class UiTestCatalog:
    """A `ui-test-catalog` document."""

    title: str
    view: str
    feature_files: tuple[FeatureFile, ...]


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
    anchor: str
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
        groups=_groups(
            entities,
            lambda entity: _entity_view(entity, view, held, under[entity.entity_id]),
            lambda entity: entity.type,
        ),
        not_loaded=tuple(_not_loaded(warning) for warning in shown if warning.entity_id not in held),
    )


def _groups(
    records: Sequence[Any], build: Callable[[Any], Any], type_of: Callable[[Any], str]
) -> tuple[EntityGroup, ...]:
    """Records grouped by entity type in the canon's order, each group in input order; an empty group is left out."""
    groups = []
    for doc_type, heading in _GROUPS:
        members = tuple(build(record) for record in records if type_of(record) == doc_type)
        if members:
            groups.append(EntityGroup(heading=heading, entities=members))
    return tuple(groups)


def _entity_view(entity: Entity, view: str, held: set[str], not_loaded: tuple[NotLoaded, ...]) -> EntityView:
    return EntityView(
        id=entity.entity_id,
        anchor=anchor(entity.entity_id),
        title=entity.title,
        badges=_entity_badges(entity, view),
        inner=_inner_only(entity, not_loaded) if view == INNER else InnerOnly((), None, (), ()),
        body=EntityBody(
            paragraphs=_paragraphs(entity.narrative) + _paragraphs(entity.purpose),
            facts=_entity_facts(entity, held),
            outlines=_present_outlines(
                ("Business value", entity.business_value),
                ("Preconditions", entity.preconditions),
                ("Not in scope", entity.not_in_scope),
                ("Notes", entity.notes),
            ),
            pages=tuple(_page(page, held) for page in entity.pages),
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


def _entity_facts(entity: Entity, held: set[str]) -> tuple[Fact, ...]:
    """Every one-line field an entity carries, in a fixed order; an empty field is left out."""
    facts = [
        Fact(label="Source", values=(_source_link(entity.source_ref),)),
        _fact("Linked issue", [entity.source], link=True),
        _fact("Tags", entity.tags),
        _fact("Surface", [entity.surface_type]),
        _fact("Type", [entity.func_type]),
        _fact("Owners", entity.owners),
        _relation("Parent", [entity.parent], held),
        _relation("User stories", entity.user_stories, held),
        _relation("Functionalities", entity.functionalities, held),
        _relation("Feature dependencies", entity.feature_dependencies, held),
        _fact("External dependencies", entity.external_dependencies),
        _fact("Wizard steps", entity.wizard_steps),
        _relation("Superseded by", [entity.superseded_by], held),
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


def _page(page: PageRef, held: set[str]) -> Page:
    facts = (_fact("Owners", page.owners), _relation("Functionalities", page.functionalities, held))
    return Page(
        route=page.route,
        page_object=page.page_object,
        primary=page.is_primary,
        purpose=page.purpose,
        facts=tuple(fact for fact in facts if fact.values),
        notes=_outline(page.notes),
    )


def _criterion(criterion: AcceptanceCriterion) -> Criterion:
    return Criterion(
        id=criterion.id,
        header=criterion.canonical_header(),
        description=" ".join(criterion.description.split()),
        lifecycle=_lifecycle(criterion),
        variants=_variants(criterion),
        rationale=criterion.rationale or None,
        also=_present_outlines(
            ("Also requires", criterion.preconditions), ("Also not in scope", criterion.not_in_scope)
        ),
    )


def _lifecycle(criterion: AcceptanceCriterion) -> Optional[str]:
    """The criterion's lifecycle row: its removal, its target version, or the backlog."""
    if criterion.removal_planned is not None:
        return f"removal planned v{criterion.removal_planned}"
    if criterion.state == "planned":
        return f"planned v{criterion.version}" if criterion.version else "backlog"
    return None


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
    return UiTestCatalog(
        title=title or DEFAULT_TITLES["ui-test-catalog"],
        view=document.document.view,
        feature_files=tuple(
            FeatureFile(
                name=catalog.feature_file,
                user_stories=tuple(_linked_group(group) for group in catalog.linked_to_user_story),
                functionalities=tuple(_linked_group(group) for group in catalog.linked_to_functionality),
                unlinked=tuple(_scenario(scenario) for scenario in catalog.unlinked),
            )
            for catalog in document.feature_files
        ),
    )


def _linked_group(group: LinkedScenarios) -> LinkedGroup:
    return LinkedGroup(entity_id=group.entity_id, scenarios=tuple(_scenario(scenario) for scenario in group.scenarios))


def _scenario(scenario: Scenario) -> ScenarioView:
    return ScenarioView(
        id=scenario.scenario_id,
        title=scenario.title,
        tags=tuple(scenario.tags),
        covers=tuple(Covered(ac_id=link.id, aspect=link.aspect) for link in scenario.acceptance_criteria),
        source=_source_link(scenario.source_ref),
    )


# ---------------------------------------------------------------------------
# coverage-matrix
# ---------------------------------------------------------------------------


def _coverage_matrix(document: CoverageMatrixResult, title: str) -> CoverageMatrix:
    view = document.document.view
    planned = document.planned_summary
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
        groups=_groups(document.entities, _coverage_entity, lambda entity: entity.type),
    )


def _coverage_entity(entity: EntityCoverage) -> CoverageEntity:
    return CoverageEntity(
        id=entity.entity_id,
        anchor=anchor(entity.entity_id),
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
    entities: list[str] = []
    scenarios: list[ScenarioView] = []
    for feature_file in presentation.feature_files:
        for group in feature_file.user_stories + feature_file.functionalities:
            entities.append(group.entity_id)
            scenarios.extend(group.scenarios)
        scenarios.extend(feature_file.unlinked)
    covered: dict[str, list[str]] = {}
    for scenario in scenarios:
        for cover in scenario.covers:
            values = covered.setdefault(cover.ac_id, [])
            if cover.aspect and cover.aspect not in values:
                values.append(cover.aspect)
    return {
        "view": presentation.view,
        "entities": _unique(entities),
        "acceptance_criteria": list(covered),
        "aspects": [{"ac_id": ac_id, "label": None, "values": values} for ac_id, values in covered.items() if values],
        "badges": [],
        "scenarios": _unique([scenario.id for scenario in scenarios]),
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


def anchor(entity_id: str) -> str:
    """An entity's place in its document: the anchor a renderer derives from a heading that holds the id alone."""
    return re.sub(r"[^a-z0-9_ -]", "", entity_id.lower()).replace(" ", "-")


def _url_link(text: str, url: Optional[str]) -> Link:
    """`text` linked to `url` only when `safe_href` keeps it; a rejected link shows as its text."""
    return Link(text=text, href=safe_href(url) if url else None)


def _fact(label: str, values: Sequence[Optional[str]], link: bool = False) -> Fact:
    """A fact of the values that are set; `link` links each one `safe_href` keeps, and shows the rest as text."""
    return Fact(label=label, values=tuple(_url_link(v, v) if link else Link(text=v) for v in values if v))


def _relation(label: str, targets: Sequence[Optional[str]], held: set[str]) -> Fact:
    """Entity ids linked to their place in this document; an id the document does not hold shows as text."""
    return Fact(
        label=label,
        values=tuple(Link(text=t, anchor=anchor(t) if t in held else None) for t in targets if t),
    )


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
