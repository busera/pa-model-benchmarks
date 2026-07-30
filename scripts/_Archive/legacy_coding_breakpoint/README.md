# Archived strict-JSON coding breakpoint suite

Archived on 2026-07-30 at Andrew's direction. Nothing was deleted.

## Contents

- `strict_json_breakpoint_runner.py` — historical producer that required generated Python inside an exact JSON `files` envelope and compared monolithic/atomized modes.
- `legacy_contract_tests.py` — its historical active test surface, retained as evidence but deliberately renamed so current pytest collection does not treat it as maintained behavior.

## Status

This suite is **legacy and non-authoritative**. Its strict JSON transport can measure source-code serialization failures rather than ordinary coding ability. Historical artifacts and reports remain valid only as evidence for that legacy contract and are not comparable to format-neutral workspace results.

The active replacement is:

- `scripts/coding_workspace_benchmark.py`
- `scripts/test_coding_workspace_benchmark.py`
- `scripts/test_coding_workspace_benchmark_regression.py`

The replacement assigns one host-selected file per model call, accepts raw or normally fenced Python, writes code into an isolated workspace, and runs compilation plus sandboxed hidden tests with bounded correction passes.
