# How to Contribute?

## **Identifying and Reporting Bugs**

* **Ensure the bug has not already been reported** by searching our **[GitHub Issues](https://github.com/AbsaOSS/generate-release-notes/issues)**.
* If you cannot find an open issue describing the problem, use the **Bug Report** GitHub issue template to open a new one.

## **Proposing New Features**

* **Check if the feature has already been requested** by searching through our **[GitHub Issues](https://github.com/AbsaOSS/generate-release-notes/issues)**.
* If the feature request doesn't exist, feel free to create a new one, using the **Feature Request** GitHub issue template.

## Branch Naming

Branches have to start with one of the allowed prefixes: `feature/`, `fix/`, `docs/`, `chore/`
Examples:
- `feature/add-hierarchy-support`
- `fix/567-handle-empty-chapter`
- `docs/improve-contribution-guide`
- `chore/update-ci-python-version`
  
Rename if needed before pushing:
```shell
git branch -m fix/<new-name>
```
Use lowercase **kebab-case** and reflect actual scope.

## PR Naming

PR titles have to carry the related issue number, using one of these formats: `#123: Title` or `123 - Title`.
Examples:
- `#567: Handle empty chapter`
- `123 - Improve contribution guide`

## PR Description

PR body has to also include these sections: `## Overview`, `## Release Notes`, `## Related`.
- **Overview** – what changed and why.
- **Release Notes** – short, user-facing summary for the changelog.
- **Related** – link the issue with a closing keyword, e.g. `Closes #123` or `Fixes AB#12345`.

## Target Branches

PRs have to target `main`, `master`, `support/*`, or `release/*`.

### Community and Communication

If you have any questions or need help, don't hesitate to reach out through our GitHub discussion section!

#### Thanks!
