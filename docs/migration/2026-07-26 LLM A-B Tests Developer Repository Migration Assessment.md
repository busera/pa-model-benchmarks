---
title: "LLM A-B Tests Developer Repository Migration Assessment"
date: 2026-07-26
type: project-decision
status: executed-superseded
area: "PA Development / LLM A-B Tests"
tags:
  - pa-development
  - benchmark-governance
  - repository-migration
---
# LLM A-B Tests Developer Repository Migration Assessment
[[2026-07-26]]

> Historical assessment, superseded by the executed migration recorded in `MIGRATION_MANIFEST.json`. The migration sequence below was the pre-execution recommendation; the actual move used copy-first backup, portability verification, archive-without-deletion, and exact staged-tree review in the dedicated repository.

## Recommendation

Move the executable LLM benchmark project out of the knowledge base into a dedicated Git repository.

`.`

Retain the canonical human decision notes and benchmark reports in your knowledge base. This should follow the established pattern: Developer is authoritative for code/runtime evidence; the knowledge base is authoritative for decisions, interpretation, and project notes.

The original recommendation was to delay execution until PA hardening was release-bound in the vault. During execution, a full backup and byte-verified copy were taken first, then hardening continued only in the dedicated repository so the selective vault worktree could no longer obscure executable bytes. The final Developer tree is independently verified before its initial Git commit.

## Evidence

- Current project size: approximately **77 MB**.
- `artifacts/`: approximately **73 MB** and **11,150 files**.
- Whole project: about **11,931 ignored files**, but only **37 Git-tracked files** at the vault root.
- Current code includes tracked, untracked, and ignored producer files under a selective vault repository. A vault commit therefore does not reliably identify all executable benchmark bytes.
- The project contains both the PA Model Benchmark and the separate Coding Model Benchmark. Their shared location contributed to a scope conflation; a dedicated repo can retain shared infrastructure while enforcing explicit suite boundaries.
- Several runners and historical manifests contain vault-absolute paths or depend on `../LLM Prompt Guides`; these must be removed or configured before the Developer repo can be called standalone and reproducible.

## Target authority split

### Developer repository — authoritative

- shared benchmark library and transport contract;
- PA D/R/W/F/T/X/tool-live suites;
- Coding Model Benchmark suite as a clearly separate package/directory;
- tests, fixtures, scorer code, schemas, prompt-profile snapshots, CLI entry points;
- technical README, CHANGELOG, release manifests, and migration tooling;
- generated artifacts in a Git-ignored `artifacts/` directory;
- a small allow-listed `evidence/releases/<run-id>/` set only when a release needs durable machine-readable evidence.

### Knowledge base — authoritative

- benchmark index and routing decisions;
- human-adjudicated reports and comparison notes;
- project decision records, methodology interpretations, and follow-up backlog;
- links to the Developer repository, exact commit/tree, run ID, and retained release-evidence manifest.

Do not keep a symlinked copy of the Developer repo inside the vault; that would reintroduce indexing/sync noise and ambiguous authority.

## Proposed repository structure

```text
./
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── src/pa_benchmarks/
│   ├── core/                 # scheduling, manifests, transport, semantics
│   ├── suites/pa/            # D/R/W/F/T/X/tool-live
│   └── suites/coding/        # coding goals, sandbox, hidden-test contracts
├── tests/
├── prompts/                  # repo-owned, hashed prompt-profile snapshots
├── docs/technical/
├── evidence/releases/        # small governed release evidence only
└── artifacts/                # generated, local, Git-ignored
```

One repository is preferable initially because both programmes share scheduling, manifest, prompt-profile, and transport infrastructure. Package boundaries and separate CLIs/reports should prevent result conflation. Split repositories later only if their release cadence or privacy boundaries diverge materially.

## Migration sequence

1. Historical proposal: finish and commit/release-bind the current PA hardening revision in its existing location. Actual execution instead froze and backed up the vault surface, copied it, then completed hardening and release binding in the dedicated repository.
2. Freeze an exact source inventory: tracked, untracked, ignored, generated, private, and obsolete files.
3. Create a timestamped full backup outside both the vault and target repository.
4. Build the Developer repository by **copying**, not moving, the reviewed source set first.
5. Separate `suites/pa` and `suites/coding`; make shared dependencies explicit.
6. Replace vault-relative and `your knowledge base` runtime dependencies with repo-owned fixtures or explicit configuration. Unknown/missing configuration must fail closed.
7. Add `pyproject.toml`, clean-export tests, source-hash coverage, and a Git-ignore policy for generated artifacts/caches.
8. Copy historical artifacts to the new ignored artifact store or an external archive; retain a manifest with file counts and hashes.
9. Run old-versus-new parity: full tests, all zero-model-call self-tests, manifest equality where expected, selected artifact hashes, and one bounded live smoke only after approval.
10. Update vault reports/index with the new repo path and exact commit/tree. Keep notes in the vault.
11. Archive the old executable vault surface only after parity and link checks. No permanent deletion; any eventual deletion requires the operator's separate exact `DELETE` confirmation.

## Migration gates

- Target repo is independently Git-versioned and runnable from a clean clone/export.
- Every executable source named by manifests is tracked.
- PA and Coding suites have separate entry points, documentation, result schemas, and promotion authority.
- No runtime dependency on the knowledge base unless explicitly configured for a private/local fixture and recorded in the manifest.
- `artifacts/`, caches, generated workspaces, and model outputs are ignored by default.
- Canonical knowledge base reports resolve to an exact Developer commit/tree and release-evidence manifest.
- Old/new test and self-test parity passes before the old path is archived.

## Decision

**Executed.** The migration was justified by reproducibility, Git hygiene, knowledge base indexing noise, artifact volume, and clearer suite boundaries. It is a code/docs authority split, not a wholesale move of benchmark knowledge out of the knowledge base. `MIGRATION_MANIFEST.json` and the Developer repository state supersede this proposal for current status.
