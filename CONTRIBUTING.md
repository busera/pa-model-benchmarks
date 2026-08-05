# Contributing

Thank you for your interest in contributing to the PA Model Benchmark Suite!

## Scope

This project evaluates LLMs for personal assistant (PA) workloads across multiple benchmark lanes. Contributions should improve the suite's fairness, coverage, portability, or documentation.

## Getting started

1. Fork the repository and clone it locally.
2. Install in editable mode: `pip install -e .`
3. Run the test suite: `python3 -m pytest -q`
4. Run all self-tests: see the verification commands in `README.md`.

## Development workflow

1. **Read the standards** — `docs/standards/benchmark-operating-standard.md` is the canonical engineering standard. Read it before making changes.
2. **Find or create an issue** — discuss what you want to change before writing code.
3. **Create a branch** — use a descriptive name (e.g., `add-f-lane-task`, `fix-identity-check`).
4. **Make focused changes** — each PR should address one concern.
5. **Add tests** — every change needs regression coverage. Run `python3 -m pytest -q` before committing.
6. **Run self-tests** — all lane runners must pass `--self-test`.
7. **Open a PR** — describe what changed and why.

## Code standards

- Python 3.11+ with type hints.
- Small, focused functions with explicit error handling.
- Behavior-focused tests with dependency injection.
- No weakening of validators, identity checks, privacy controls, or completion gates.
- Fixtures must be synthetic and non-personal. Never commit real data.

## What we accept

- **New benchmark tasks** — additional cells in any lane, with validators and tests.
- **New model profiles** — prompt profiles and guides for additional model families.
- **Bug fixes** — corrections to validators, scheduling, identity checks, or telemetry.
- **Documentation** — improvements to ADOPTION.md, README.md, or inline docs.
- **Portability** — making the suite work on additional platforms.

## What we don't accept

- Changes that weaken validators to improve a model's score.
- Personal data, real credentials, or private fixture content.
- Model output used to tune scored fixtures.
- Universal model rankings that ignore category separation (local vs. cloud).
- Changes that remove or bypass required lanes, repeat requirements, or identity checks.

## Fairness rules

The suite's fairness rules are documented in `README.md`. All contributions must respect:

1. Exact-tag model resolution (no family substring matching).
2. Invariant objectives, validators, and acceptance criteria across models.
3. Separate local and cloud decision populations.
4. Immutable run artifacts (no overwrite, splice, or repair).
5. Synthetic, non-personal fixtures for all tracked tests.

## Review process

- All PRs run CI (pytest + self-tests).
- Harness, migration, promotion, or routing-grade changes require independent review.
- Maintainers may request changes to ensure fairness, coverage, or portability.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
