# MB-006 Current-Candidate TDD and Verification Evidence

## Scope

Current two-model streaming-proxy and strict-serial candidate, after the independent FAIL verdict on reviewed fingerprint `0d8756165478aad9e7c31d4e1404b8b86dbf495686bbcddf247ec0cb75669f90`.

## Focused RED

Retained outside the repository at:

`/tmp/benchmark-pa-model-evidence/20260805-current-remediation/focused-red.txt`

Observed before implementation:

- tool-live current-candidate tests: `5 failed, 12 passed`;
- serial-runner tests before implementation: `4 failed`;
- preflight total-exposure tests before implementation: `2 failed, 2 passed`;
- D/H externally governed preflight-skip semantics before implementation: `2 failed`.

The failures covered missing usage, missing finish telemetry, truncation, unproven thinking control, digest drift, L03 session attribution, missing serial orchestration and missing preflight exposure accounting.

## Focused GREEN

Command:

```bash
python3 -m pytest -q \
  scripts/test_mb006_preflight.py \
  scripts/test_mb006_candidate_runner.py \
  scripts/test_pa_tool_live_benchmark.py
```

The exact three-file command above now produces `38 passed` after the third remediation added authentic aggregate-shape, envelope-distribution and pre-call root-boundary regressions. The prior `27 passed` statement was incorrect and is superseded by the reproducible commands below.

## Second independent-review remediation

Retained RED output:

`/tmp/benchmark-pa-model-evidence/20260805-review2-remediation/focused-red.txt`

The current-candidate RED runs produced `11 failed, 4 passed`, followed by one focused symlink-escape failure, for run-ID confinement, resolved descendant enforcement, complete/unique evidence verification, T07 two-call retention, and zero-retry Hermes configuration.

Exact focused GREEN command:

```bash
python3 -m pytest -q \
  scripts/test_mb006_candidate_runner.py \
  scripts/test_pa_tool_live_benchmark.py::test_isolated_home_uses_recording_proxy_endpoint \
  scripts/test_t_matrix_reliability.py::test_t7_artifact_retains_both_provider_call_envelopes
```

The second-remediation result was `16 passed`; the same focused command now produces `19 passed`.

## Third independent-review remediation

Retained RED output:

`/tmp/benchmark-pa-model-evidence/20260805-review3-remediation/focused-red.txt`

RED: `4 failed, 13 passed`. GREEN: candidate-runner `17 passed`; exact focused command `19 passed`; exact three-file command `38 passed`; full suite `206 passed`. Compilation, nine execution self-tests, deterministic no-call preflight and `git diff --check` passed.

## Evidence and serial-lock redesign implementation

Approved plan: `docs/plans/2026-08-05-mb006-evidence-lock-redesign.md`, SHA-256 `0fdb3a5420a8e99adb94c98c3e8986d909def7401de6fb1d124c3f1d7c92cfd7`.

Pre-change backup: `/tmp/change-backups/20260805-104835-mb006-evidence-lock-redesign-t_38cc85d8/`. Its `MANIFEST.txt` binds HEAD `37bd3a258d956e804340424133286af34fca3a9d`, the pre-change Git diff/status fingerprints and per-file SHA-256 values.

Strict focused RED-before-GREEN evidence:

- Cluster A, typed identities and canonical fingerprints: RED `6 failed, 24 deselected`; GREEN `7 passed, 23 deselected`.
- Cluster B, frozen 48-call schedule, lifecycle matrix, T07 `[80, 500]`, canonical request/raw response evidence and chaining: initial RED `11 failed, 23 deselected`; raw-artifact RED `3 failed, 25 deselected`; shifted-order regression RED `1 failed, 33 deselected`; final focused GREEN included below.
- Cluster C, descriptor-level no-follow lock and zero-side-effect contention boundary: RED `5 failed, 28 deselected`; GREEN `5 passed, 28 deselected`.
- Cluster D, HEAD/status/kind/mode/content tree and credential gate: RED `6 failed`; one FIFO-fixture correction exposed `1 failed, 5 passed`; GREEN `6 passed`.

Final focused commands and results:

```bash
PY=/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3
"$PY" -m pytest -q scripts/test_benchmark_transport.py -k 'call_identity or call_record or fingerprint or call_schedule'
# 7 passed, 23 deselected

"$PY" -m pytest -q scripts/test_t_matrix_reliability.py scripts/test_mb006_candidate_runner.py -k 't07 or call_schedule or authentic_t or serial_lock or symlink or hardlink or path_swap or call_lifecycle or call_artifacts'
# 19 passed, 23 deselected

"$PY" -m pytest -q scripts/test_mb006_tree_gate.py
# 6 passed

"$PY" -m pytest -q scripts/test_mb006_preflight.py scripts/test_mb006_candidate_runner.py scripts/test_pa_tool_live_benchmark.py scripts/test_t_matrix_reliability.py
# 63 passed
```

Stable-candidate verification:

```bash
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), sys.version; print(sys.version)'
# Python 3.12.13 (Anaconda; Clang 20.1.8)

"$PY" -m pytest -q
# 239 passed

"$PY" -m py_compile scripts/benchmark_transport.py scripts/run_t01_t12_full_matrix_profiled.py scripts/mb006_candidate_runner.py scripts/mb006_tree_gate.py
# exit 0

# All nine named runner --self-test commands
# pass; each reports model_calls=0 where applicable

"$PY" scripts/mb006_preflight.py --json > /tmp/runtime-tmp/mb006-redesign-preflight.json
# validation=pass; direct=231; candidate caps=279 scored/280 total;
# aggregate caps=558 scored/560 total; model_calls=0

"$PY" scripts/mb006_tree_gate.py --output /tmp/runtime-tmp/mb006-redesign-tree-gate.json --json
# exit 0; manifest_valid=true; credential_hits=[]; errors=[]; model_calls=0

git diff --check
# exit 0
```

No provider/model call, candidate preflight execution, Hermes configuration change, commit, push or branch change occurred during implementation or verification.

## Terminal-ledger append-failure lifecycle remediation

Pre-change backup: `/tmp/change-backups/20260805-113823-t_2f9018d8-append-failure/`.

Strict RED covered all five post-start terminal append sites (`failed_transport`, response-artifact `failed_contract`, `failed_parse`, `failed_identity`, and `completed`) plus outer-runner retention. Every case used a fake provider response or exception and made no network/model call:

```bash
"$PY" -m pytest -q -vv scripts/test_t_matrix_reliability.py \
  -k 'terminal_append_failure or outer_runner_retains_carried_terminal_event'
# RED: 6 failed, 10 deselected
```

The centralized terminal finalizer now always constructs one terminal event, attempts one append, and raises `ProviderCallLifecycleError` carrying `(started, terminal)` if either the provider path or terminal persistence fails. The original provider failure remains the explicit cause where present; the terminal persistence failure remains an explicit attribute and exception note. `exception_checks` retains the constructed lifecycle and a bounded terminal-persistence error record so `run_part` remains fail-closed.

```bash
"$PY" -m pytest -q -vv scripts/test_t_matrix_reliability.py \
  -k 'terminal_append_failure or outer_runner_retains_carried_terminal_event or response_artifact_persistence_failure'
# GREEN: 7 passed, 9 deselected

"$PY" -m pytest -q scripts/test_t_matrix_reliability.py scripts/test_benchmark_transport.py
# 46 passed

"$PY" -m pytest -q
# 246 passed
```

Compilation of the three modified Python files passed. All nine named no-call self-tests passed, the deterministic MB-006 preflight returned `validation=pass` with direct/scored/total caps `231/279/280` per candidate and `558/560` aggregate, and `model_calls=0` remained unchanged.

## No-call boundary

These focused tests and each runner `--self-test` make zero provider-generation calls. Provider preflight and scored execution remain prohibited until full verification, credential scan, exact tree hash and fresh independent review pass.
