# Legacy result fixture provenance

This compact fixture preserves real top-level rows from
`results/20260714_121237_claude1_parameter_sweep`, generated on 2026-07-14 before
`result_manifest.json` was introduced. The original result used long timestamped
case directories; the fixture intentionally retains only the primary
`sweep_summary.csv` rows needed for compatibility regression testing.

Do not rewrite this fixture into the current schema. It is immutable input evidence
for the legacy reader.
