# Decision and report authority

Canonical PA human decisions, PA benchmark interpretation, routing reports, and the PA benchmark index remain in a separate decision/report authority (e.g., a project management system, knowledge base, or document store).

This Developer repository is authoritative for PA executable source, tests, fixtures, prompt-guide snapshots, technical release manifests, and generated local PA artifacts. A separate coding-benchmark project owns coding-specific evaluation.

Every promoted result should bind both authorities:

1. exact Developer Git commit/tree and run ID;
2. retained release-evidence manifest;
3. linked decision/report in the separate authority.
