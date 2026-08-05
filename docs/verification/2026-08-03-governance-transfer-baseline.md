# Governance Transfer Baseline — 2026-08-03

- Target repository: `.`
- Source-method programme: `../benchmark-coding`
- Baseline target commit: `37bd3a258d956e804340424133286af34fca3a9d`
- Baseline Git status: clean `main`
- Baseline test command: `python3 -m pytest -q`
- Baseline result: `139 passed in 0.26s`
- Backup: `/tmp/benchmark-pa-model-governance-transfer-20260803_103305`

## Current working-tree verification

- Focused selector/transport/daily/held-out tests: `99 passed in 0.24s`
- Full suite after independent-review remediation: `168 passed in 0.30s`
- Eight runner self-tests: passed; `model_calls=0`
- `py_compile`: passed
- `git diff --check`: passed
- First independent exact-working-tree review: `NO-GO` (`P0=0`, `P1=3`, `P2=2`).
- Second independent exact-working-tree review: `NO-GO` (`P0=0`, `P1=0`, `P2=2`); both residual findings were remediated and require final re-review before release.
- Final independent exact-working-tree review: `GO` (`P0=0`, `P1=0`, `P2=0`).
- Review boundary: the final GO covers the implementation working tree reviewed before the bounded state/backlog/handoff refresh. The later governance-refreshed tree is a separate unreviewed identity and must not be described as covered by that verdict.

This change transfers methods and governance only. It does not transfer coding scores, fixtures, hidden tests, reports, or routing authority, and it performs no model calls or live routing changes.
