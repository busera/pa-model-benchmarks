# Legacy T-Matrix Fixture Provenance

These modules are project-owned snapshots of the original T01–T12 fixture and deterministic scorer implementations.

| Project file | Original source | SHA-256 at migration |
|---|---|---|
| `wave1.py` | `/Users/busera/Temp/Hermes/ollama_cloud_pa_wave1.py` | `7558da7cc2bc2d7b57b1f770d4a9078e35f791afd7e910e70bb2e03def764c6a` |
| `wave2.py` | `/Users/busera/Temp/Hermes/ollama_cloud_pa_wave2.py` | `7e7a7214795c6d03c9c4366521c5b7ac9456fd21a0c1ddb4b2a9f7b980230117` |

Migrated on 2026-07-11. The copied fixture/scorer content was unchanged during migration. Future changes must be made here with regression tests; `/Users/busera/Temp/Hermes` is no longer an executable dependency.

`wave2.py` retains historical real-source loader functions only as migration provenance. The maintained T runner never invokes them: T06 uses `FIXTURE_T1` and `FIXTURE_T4`, and regression tests fail if either real-source loader is called. Therefore the maintained T01–T12 execution remains synthetic and may be used with the declared synthetic privacy class.
