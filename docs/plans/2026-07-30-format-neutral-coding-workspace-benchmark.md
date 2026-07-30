# Format-Neutral Coding Workspace Benchmark Implementation Plan

> **For Hermes:** Implement this plan with strict RED/GREEN verification and independent review.

**Goal:** Replace the active strict-JSON coding producer with a repository-owned workspace benchmark that accepts ordinary raw or fenced code per requested file, while archiving the legacy producer without deleting evidence.

**Architecture:** Preserve the frozen goal specifications and hidden tests. Each model call owns one allow-listed file and receives the full goal plus current workspace context. A deterministic extractor accepts either raw source or one standard fenced code block, writes it to the declared path, compiles that generated file immediately, and runs hidden pytest tests against the complete workspace in the existing Seatbelt sandbox. Multi-file goals are generated sequentially in declared dependency order; no generated path or JSON file envelope is accepted from the model.

**Tech Stack:** Python 3.12 stdlib, pytest, macOS Seatbelt, Ollama/Hermes transports already owned by the repository.

## Acceptance criteria

1. Active coding prompts do not request JSON, path metadata, patches, or another transport schema.
2. Raw Python and one fenced code block produce identical file bytes; explanatory prose around one fence is tolerated.
3. Empty output, unterminated fences, multiple competing code blocks, and non-Python language fences fail explicitly before execution.
4. Every model call writes exactly one host-selected allow-listed file; model output cannot choose or escape its destination.
5. Multi-file goals run sequentially with current workspace context and hidden tests remain sandboxed and isolated from parent pytest configuration.
6. Legacy strict-JSON runner/tests are retained under `scripts/_Archive/legacy_coding_breakpoint/` and are no longer active/imported by repository verification.
7. Focused tests, the full suite, offline self-test, compilation, lint/diff hygiene, clean-export tests, and a mocked end-to-end workspace smoke pass.
8. Historical strict-JSON artifacts remain unchanged and are labelled legacy/non-comparable in current documentation.
9. Correction passes can reach a later file that failed compilation; stale later files cannot abort an earlier-card rewrite before that failed file is regenerated.
10. Pytest completion evidence authenticates both completed PASS and completed FAIL outcomes, while premature exit, skipped census, collection mismatch, and generated-code collection errors remain fail-closed and separately attributable.
11. Ollama evidence requires affirmative completion, non-truncation, and matching returned-model identity; Hermes maximum-iteration warnings fail closed and unavailable returned-model identity remains diagnostic/unverified.
12. Resume requires the canonical terminal artifact for every retained result, binds it to the exact schedule slot and artifact path, and rejects missing or conflicting duplicates.

## Ordered execution task list

1. **RED extraction contract**
   - Create `scripts/test_coding_workspace_benchmark.py` from the maintained behavior tests.
   - Add failing cases for raw code, fenced code with prose, empty/ambiguous/non-Python responses, no response-format schema, and one-file-per-call prompts.
   - Verify focused RED failures are caused by the missing active runner/behavior.
2. **GREEN active runner**
   - Create `scripts/coding_workspace_benchmark.py` from the proven scheduling/sandbox/reporting substrate.
   - Remove JSON schema/file-envelope parsing and monolithic mode.
   - Add `extract_source_response`, host-owned per-file prompts, and sequential workspace generation.
   - Verify focused GREEN tests.
3. **Archive legacy producer**
   - Move strict-JSON runner and its historical tests to `scripts/_Archive/legacy_coding_breakpoint/` with an archive README.
   - Update active portability/import checks to target `coding_workspace_benchmark`.
4. **Documentation/governance**
   - Update `README.md`, `PROJECT_STATE.md`, `CHANGELOG.md`, and the authoritative Obsidian benchmark backlog with the new non-comparable v2 contract and archive location.
5. **Verification and review**
   - Run focused tests, full pytest, runner self-test, `py_compile`, Ruff/diff checks, and clean-export pytest.
   - Independently review the exact diff; remediate findings and rerun gates.
   - Commit only the scoped archive/new-runner/tests/docs changes.

## Risks and rollback

- Historical scores are not comparable to the format-neutral v2 suite; documentation must say so.
- Sequential per-file generation measures a workspace coding workflow, not one-shot monolithic serialization.
- Deterministic extraction must remain narrow to avoid executing arbitrary prose.
- Rollback backup: `/Users/busera/Temp/Hermes/change-backups/20260730-format-neutral-coding-suite/`.
- No historical artifacts, routing, provider configuration, or model data will be deleted or changed.
