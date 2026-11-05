"""Tests for internal documentation links."""

from tests.docs.pages import _resolved_links


def test_link_climbing_above_repository_root_is_not_resolved() -> None:
    """A relative link above the repository root is not treated as internal."""
    assert _resolved_links("docs/action.md", "[outside](../../../outside.md)") == set()
