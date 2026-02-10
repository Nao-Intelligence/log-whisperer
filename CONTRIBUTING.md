# Contributing to LogWhisperer

Thank you for considering contributing to LogWhisperer! This guide will help you get started.

## Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/log-whisperer.git
cd log-whisperer
```

### 2. Set up the development environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Run tests

```bash
pytest tests/ -v
```

All tests must pass before submitting a PR.

## Branch Naming Convention

**This is critical.** Our CD pipeline automatically determines the version bump from the branch name prefix. Use the correct prefix for your change:

| Prefix | Version Bump | Use When |
|---|---|---|
| `feat-*` or `feature-*` | **minor** (0.X.0) | Adding new functionality |
| `fix-*` or `bugfix-*` or `hotfix-*` | **patch** (0.0.X) | Fixing a bug |
| `breaking-*` or `major-*` | **major** (X.0.0) | Making breaking/incompatible changes |
| `docs-*` | patch | Documentation only |
| `chore-*` | patch | Maintenance, CI, dependencies |
| `refactor-*` | patch | Code restructuring without behavior change |
| `test-*` | patch | Adding or updating tests |
| `perf-*` | patch | Performance improvements |

**Examples:**

```
feat-json-export
fix-docker-timeout
breaking-config-schema-v2
docs-update-readme
chore-update-dependencies
```

## Making Changes

1. Create a branch from `main` using the naming convention above.
2. Make your changes in small, focused commits.
3. Add or update tests for any new or changed behavior.
4. Ensure all tests pass: `pytest tests/ -v`
5. Push your branch and open a pull request against `main`.

## Pull Request Guidelines

- Keep PRs focused on a single change.
- Fill out the PR template when opening a pull request.
- Link any related issues (e.g., "Closes #42").
- All CI checks must pass before merging.
- A maintainer will review your PR and may request changes.

## Code Style

- Follow existing patterns in the codebase.
- Keep functions and modules focused — do one thing well.
- Use meaningful variable and function names.
- Add comments only where the logic isn't self-evident.

## Reporting Bugs

Use the [bug report template](https://github.com/Nao-Intelligence/log-whisperer/issues/new?template=bug_report.md) to file a bug. Include:

- Steps to reproduce
- Expected vs. actual behavior
- Python version and OS
- Relevant log output

## Suggesting Features

Use the [feature request template](https://github.com/Nao-Intelligence/log-whisperer/issues/new?template=feature_request.md) to propose new ideas.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
