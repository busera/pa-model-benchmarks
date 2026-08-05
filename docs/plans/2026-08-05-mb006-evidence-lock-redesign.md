# MB-006 Evidence and Serial-Lock Contract Redesign

## Scope

Replace the unstable post-hoc T-lane evidence inference and unsafe serial-lock opening boundary before any candidate call. The smallest useful architectural change is: (1) make the benchmark host emit one typed, first-class provider-call record for every actual T provider invocation, including a deterministic schedule identity and request/response fingerprints; (2) verify that ledger against the frozen expected call schedule rather than inferring distinct calls from list cardinality; and (3) acquire the global serial lock through an atomic no-follow file-descriptor contract that validates file type, ownership, permissions, link count and canonical parent before any write, registration or subprocess.

Architecture diagnosis: three targeted remediation cycles reduced findings from seven to four to two, but the third exact-candidate review remained at two findings. Evidence validation migrated from missing counts, to misdistributed counts, to duplicated-call substitution because the verifier still reasons over nested dictionaries without an authoritative call identity. Path validation migrated from run-ID traversal, to lane-root symlinks, to the lock symlink because safety checks were distributed across path consumers. The rejected workaround is another signature-specific check over list length or one more `Path.resolve()` call. Root cause: provider-call identity and exclusive-execution authority are not owned at their creation boundaries. Replacement hypothesis: host-owned call identity plus descriptor-level lock acquisition removes both unstable inference boundaries.

Change assurance: **Governed** — this code authorizes external model calls and serial promotion to the second candidate; false positives can spend quota or contaminate benchmark evidence.

## Non-goals

- Do not change prompts, fixtures, scores, weights, promotion thresholds, roster, digests, repeats, call caps or candidate order.
- Do not add retries, fallback models, concurrency or partial-run resume behavior.
- Do not alter Hermes production routing or configuration.
- Do not generalize a new repository-wide framework; limit the call-ledger contract to `benchmark_transport`, the T runner and the MB-006 candidate verifier unless an existing one-call lane needs a mechanical adapter.
- Do not start preflight or candidate calls until independent testing and exact-byte review pass.
- Do not commit or publish runtime artifacts as source.

## Acceptance Criteria

1. A frozen expected T call schedule contains exactly 48 unique identities for three repeats. Each identity is `(run_id, lane, task_id, trial_index, part, call_ordinal)`; T07 has ordinals 1 and 2 per trial, all other T parts have ordinal 1.
2. Before execution, the host writes a frozen expected-call schedule. Each actual invocation appends a `started` event before transport and exactly one terminal event on every caught exit path: `completed`, `failed_transport`, `failed_parse`, `failed_identity`, or `failed_contract`. The matrix is authoritative: expected identity with no `started` = not attempted; `started` with no terminal = interrupted/incomplete; terminal failure without response bytes = attempted/no response; terminal failure with response bytes = response received/invalid; `completed` = valid parsed provider result. Any non-completed or incomplete expected call makes the run ineligible. Exceptions must carry the finalized record/event so the runner can persist it before propagating; a process crash leaves an unmatched `started` event and therefore fails closed.
3. The call wrapper receives a host-created identity and emits typed lifecycle events containing that identity, canonical request fingerprint, optional raw-response fingerprint by state, requested/actual model, effective controls, tokens, finish evidence and elapsed time. IDs, order and cardinality are host-owned; model text cannot affect them. T07 call-2-not-attempted after call-1 failure is explicitly distinguishable from call-2 attempted-and-failed.
4. T07 call 1 and call 2 are independently bound to their expected request controls. For the current frozen contract this includes ordered `num_predict` values 80 then 500. A duplicated first-call record, swapped ordinals, duplicate ID, missing call, shifted record, changed request fingerprint, or extra call fails verification even when aggregate count remains 48.
5. Canonical request bytes are UTF-8 compact JSON with recursively sorted keys, `ensure_ascii=false`, separators `(',', ':')`, and no trailing newline over the complete effective Ollama payload: model, effective system prompt/full ordered messages, stream, keep-alive, options and model-profile top-level fields. The raw provider HTTP response body is retained as a synthetic per-call artifact and hashed byte-for-byte before parsing. The verifier reserializes retained request JSON, rehashes raw response bytes, reconstructs expected fixture/system-prompt/control fields from authoritative source code, and verifies T07 call 2 chains the exact parsed call-1 assistant content. Transport headers and local URLs are excluded from the request hash and verified separately as route metadata. Prompt/message substitution, fingerprint tampering and missing T07 call-1 raw response are regressions.
6. Authentic T output remains 51 artifact rows (45 provider-bearing part rows plus six T06/T09 aggregate rows) and 48 unique completed call identities. Aggregate rows cannot contain provider-call records and are verified separately.
7. One-call D/R/W/F/H lanes retain their existing score and artifact schemas. Their evidence verifier continues to require exact task/trial coverage, one provider envelope per expected row, complete summary, route, token, finish and elapsed evidence.
8. The global lock is opened with `os.open` using macOS `O_NOFOLLOW_ANY` when available, otherwise `O_NOFOLLOW`, combined with `O_CREAT | O_RDWR | O_CLOEXEC`, mode `0o600`, without truncation or write before validation. Absence of an effective no-follow flag is a hard failure. Immediately after open, acquire non-blocking exclusive `flock`; while locked, `fstat` must prove a regular file, current UID ownership, no group/other permissions and `st_nlink == 1`, while `lstat` identifies the same device/inode. Repeat the same inode/link-count checks immediately before the first truncate/write. Only then may the process write its PID.
9. Exact `execute_candidate` order is: read-only candidate/root validation → acquire and validate lock → re-check candidate/root/state preconditions under lock → create run root → live registration → registration/state/artifact writes → subprocesses. Lock contention or validation failure causes zero mkdir/state/registration/subprocess side effects.
10. Threat boundary: protect against prepositioned symlinks/directories/hard links, unsafe permissions, accidental compliant-process races and path substitution before first write. A hostile process with the same UID can modify the repository/code and is outside this lock’s trust boundary; the contract does not claim protection from same-UID mutation after acquisition. Deterministic path-swap tests cover the in-scope open/lock/validate/pre-write windows.
11. Existing canonical-root and planned-lane checks remain mandatory before registration/subprocess. No path check is weakened to make the redesign pass.
12. Every new production behavior follows a focused RED cluster before implementation. Frozen reviewer adversarial cases are copied as independent oracle fixtures; they are not rewritten to fit the implementation.
13. Focused tests, full pytest, Python compilation, nine zero-call self-tests, deterministic no-call preflight, `git diff --check`, repository-local scoped credential scan and exact executable-tree identity pass. The canonical tree manifest binds the exact Git HEAD OID plus every dirty path's porcelain-v2 status, object kind and mode. Regular files retain byte count and SHA-256; deletions are explicit tombstones; symlinks retain the exact link-target bytes and hash; submodules and unsupported non-regular objects are rejected. HEAD, status, kind, mode and content/link-target evidence are all included in the aggregate. A separately dispatched read-only testengineer and read-only codereview both return PASS on that same aggregate and HEAD before DeepSeek preflight.

## Files / Surfaces Likely Touched

- `scripts/benchmark_transport.py` — typed call identity/record and canonical fingerprint helper.
- `scripts/run_t01_t12_full_matrix_profiled.py` — construct T call contexts and retain the exact call records.
- `scripts/mb006_candidate_runner.py` — expected schedule verification and safe descriptor-level serial lock.
- `scripts/test_benchmark_transport.py` — call-record/fingerprint RED/GREEN tests.
- `scripts/test_t_matrix_reliability.py` — authentic T07 two-call identity and control-order tests.
- `scripts/test_mb006_candidate_runner.py` — duplicate/substitution schedule tests and symlink/hard-link lock tests.
- `scripts/mb006_tree_gate.py` — canonical HEAD/status/kind/mode/content manifest and scoped credential scan, with zero provider calls.
- `scripts/test_mb006_tree_gate.py` — canonical framing, modified/untracked/deleted census, HEAD/mode/symlink identity and credential-signature tests.
- `docs/reviews/2026-08-05-mb006-current-candidate-tdd-evidence.md` — exact RED/GREEN commands and results after implementation.
- `docs/plans/2026-08-05-mb006-evidence-lock-redesign.md` — this contract; implementation may update only realized command/count evidence, not weaken acceptance criteria.

## Execution Task List

1. Preserve the current candidate files under a new attributable `/tmp/change-backups/` boundary and record the current changed-tree hash. Do not touch the prior retained RED evidence.
2. RED cluster A — add 3–5 tests for canonical call identity/fingerprints: unique deterministic identities; complete effective prompt/message substitution changes the request hash; raw-response tampering changes the response hash; malformed/duplicate identities fail.
3. Implement the minimal frozen dataclass/helper in `benchmark_transport.py`; run cluster A GREEN and refactor only after GREEN.
4. RED cluster B — add authentic T 51-row/48-call test plus duplicated first-call, swapped ordinal, missing second call, call-2-not-attempted after call-1 failure, transport/parse/identity/contract terminal failures, unmatched-start interruption and shifted-call cases. Preserve the independent reviewer’s `[80, 80]` versus `[80, 500]` adversarial fixture.
5. Update the T runner to write the expected schedule and append `started` plus terminal lifecycle events around each provider invocation, retaining canonical request bytes and raw response bytes. Update candidate verification to compare the complete lifecycle ledger with the frozen schedule, state matrix, request reconstruction, response hashes and T07 chaining. Run cluster B GREEN.
6. RED cluster C — add lock tests proving a symlink target is byte-identical after rejection, a directory is rejected, a hard link is rejected where supported, wrong permissions are rejected, path substitution before pre-write revalidation is rejected, and a valid stale regular lock file can be safely locked/reused. Add contention tests proving no run-root mkdir, state write, registration or subprocess occurs before lock authority.
7. Replace `Path.open("a+")` with a small `safe_serial_lock()` descriptor/context-manager boundary satisfying Acceptance Criteria 8–10, and reorder `execute_candidate` exactly as Acceptance Criterion 9. Run cluster C GREEN.
8. RED cluster D — add canonical manifest/credential-scan tests proving that HEAD movement, executable-mode changes, deletions and symlink-target changes alter or invalidate identity. Implement `mb006_tree_gate.py` so the exact HEAD OID and every dirty path's porcelain-v2 status, object kind, mode and representation are repository-owned and reproducible without provider calls. Regular files use byte count/SHA-256, deletions use tombstones, symlinks hash exact link-target bytes, and submodules/unsupported non-regular objects fail closed.
9. Run affected focused tests once stable, then the full suite, compile checks, all zero-call self-tests, deterministic preflight and `git diff --check`.
10. Run `mb006_tree_gate.py`, freeze its canonical manifest/aggregate plus exact HEAD OID and do not change HEAD, status, modes, objects or bytes while testing/review runs.
11. Dispatch `testengineer` and then `codereview` as explicitly read-only cards bound to the exact aggregate and HEAD OID. Prohibit edits, remediation, commits/checkout, routing/config changes and provider/model calls. Recompute the same aggregate after each stage. Any HEAD/status/kind/mode/content change invalidates both stages and returns to implementation/full verification. Any P0/P1/P2 result blocks calls.
12. Only after both same-byte PASS results, run DeepSeek through the strictly serial candidate runner, verify its complete evidence, then allow Nemotron.

## Test / Verification Plan

Focused commands after the corresponding RED is captured:

```bash
PY=/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
"$PY" -m pytest -q scripts/test_benchmark_transport.py -k 'call_identity or call_record or fingerprint'
"$PY" -m pytest -q scripts/test_t_matrix_reliability.py scripts/test_mb006_candidate_runner.py -k 't07 or call_schedule or authentic_t or serial_lock or symlink or hardlink or path_swap'
"$PY" -m pytest -q scripts/test_mb006_tree_gate.py
"$PY" -m pytest -q scripts/test_mb006_preflight.py scripts/test_mb006_candidate_runner.py scripts/test_pa_tool_live_benchmark.py scripts/test_t_matrix_reliability.py
```

Stable-candidate checks:

```bash
PY=/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
"$PY" -m pytest -q
"$PY" -m py_compile scripts/benchmark_transport.py scripts/run_t01_t12_full_matrix_profiled.py scripts/mb006_candidate_runner.py scripts/mb006_tree_gate.py
"$PY" scripts/pa_daily_use_benchmark.py --self-test
"$PY" scripts/pa_real_life_pack_benchmark.py --self-test
"$PY" scripts/pa_typical_workload_benchmark.py --self-test
"$PY" scripts/pa_conflict_retrieval_benchmark.py --self-test
"$PY" scripts/pa_extended_capability_benchmark.py --self-test
"$PY" scripts/run_t01_t12_full_matrix_profiled.py --self-test
"$PY" scripts/pa_held_out_benchmark.py --self-test
"$PY" scripts/pa_tool_live_benchmark.py --self-test
"$PY" scripts/mb006_candidate_runner.py --self-test
"$PY" scripts/mb006_preflight.py --json > /tmp/runtime-tmp/mb006-redesign-preflight.json
"$PY" scripts/mb006_tree_gate.py --output /tmp/runtime-tmp/mb006-redesign-tree-gate.json --json
git diff --check
```

`mb006_tree_gate.py` is the repository-local authority for both final checks. Exit status must be zero and its canonical JSON must report `credential_hits: []`, `manifest_valid: true`, `head_oid`, and one sorted row per dirty path containing porcelain-v2 status, object kind and mode plus its exact representation: `{bytes, sha256}` for regular files, `{deleted: true}` for tombstones, or `{link_target_bytes, link_target_sha256}` for symlinks. Submodules and unsupported non-regular objects fail closed. The aggregate SHA-256 covers compact canonical bytes containing HEAD and all rows. Re-running it without HEAD/status/kind/mode/content changes must produce the same aggregate. Tests must prove HEAD movement, executable-bit changes, deletions and symlink-target changes alter or invalidate identity. Provider-call counters must remain zero throughout planning, implementation tests, self-tests, preflight-manifest generation, tree-gate execution, independent testing and review.

## Context7 / External Docs

`completed: /websites/python_3 — os.open returns a non-inheritable descriptor; open flags are bitwise-composable; O_NOFOLLOW is available when provided by the C library; macOS exposes the stronger O_NOFOLLOW_ANY from Python 3.10; os.lstat does not follow symlinks; fcntl.flock accepts LOCK_EX and LOCK_NB and raises OSError on failure.` Implementation must feature-detect the stronger macOS flag and fail closed if neither no-follow flag exists.

## Risks / Blockers

- `O_NOFOLLOW` platform behavior and flag availability must be confirmed against current Python/macOS documentation before implementation. Block implementation if the available runtime cannot provide an equivalent fail-closed no-follow boundary.
- A predictable safe lock can still be prepositioned for denial of service. That is acceptable fail-closed behavior; it must never overwrite/follow the object. Operational cleanup remains manual and outside this task.
- Deterministic call IDs require the run ID to be unique and immutable; existing no-retry/non-existing-root checks provide that precondition.
- Fingerprints bind evidence, not truth by themselves. The verifier must also compare structured expected identity/controls and complete provider telemetry.
- No operator design choice, credential or destructive action is currently required. Implementation remains blocked until this frozen redesign receives independent plan review.

## Downstream Handoff

Implement only after independent plan PASS. Preserve prompts, scores, roster, repeats and routing. Use four strict RED-before-GREEN clusters: typed host-owned call records; exact T lifecycle schedule including distinct T07 `[80, 500]` calls; descriptor-level no-follow serial lock plus corrected execution ordering; and the repository-owned tree/credential gate. Do not add retries or weaken existing root checks. Stop before any live model call. Verify focused tests, full suite, compilation, all nine named self-tests, deterministic no-call preflight, diff check and `mb006_tree_gate.py`; then obtain separate explicitly read-only testengineer and codereview PASS on the same aggregate.
