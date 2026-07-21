# v1.0 Release Checklist

This document defines a finite finish line for v1.0. Work outside these gates is
deferred unless it is required to fix a correctness or reproducibility defect.
The machine-readable source of truth is `release/v1.0.0.json`.

## Current decision

v1.0.0 was **released on 2026-07-21**. All five required gates completed before the
evidence-backed Build the Lab post, PR #5 merge, release CI, and `v1.0.0` tag. The
published release is
[`PySDM Seeding Lab v1.0.0`](https://github.com/Jinu219/PySDM-Seeding-Lab/releases/tag/v1.0.0).
The direct-observation review remains a conservative scope decision: neither
BASTALIAS nor ARM ENA is accepted as direct parcel-time validation, so external
calibration and field-efficacy claims are explicitly unsupported in v1.0.

Run the gate locally:

```powershell
& .\.conda\python.exe scripts\check_release_readiness.py
```

The command intentionally returns a non-zero exit code while v1.0 is incomplete.
Use `--allow-incomplete` for a structural manifest check during normal development,
or `--json` for a machine-readable report.

## Required gates

1. **Software platform — complete.** Reproducible simulation, result contracts,
   dashboards, provenance, and cross-platform CI are implemented.
2. **Real observation ingestion — complete.** BASTALIAS NetCDF ingestion and the
   mapping audit exercise the full observation workflow without overstating the
   evidence class.
3. **External-validation disposition — complete.** BASTALIAS and ARM ENA were
   reviewed and retained as proxies. No direct-temporal dataset is accepted and no
   external calibration claim is made for v1.0.
4. **Scientific scope review — complete.** The release is classified as a research
   workflow; supported, descriptive, operational-only, and unsupported claims are
   fixed in `release/v1_scientific_scope.json` and `docs/V1_SCIENTIFIC_SCOPE.md`.
5. **Release candidate — complete.** Version and changelog are frozen, the
   end-to-end release contract is machine checked, and Windows/Ubuntu CI plus real
   PySDM integration are the final remote acceptance checks for the candidate commit.

Serial versus 4/8-worker server benchmarking is deferred to v1.1. It is useful
operational work, but it is not required to establish v1.0 scientific validity.

## Push, blog, merge, and tag policy

Routine, reviewed development commits may be pushed to `develop` without stopping
for a blog post. A push to `develop` is **not** a release or merge checkpoint.

When all five required gates are complete:

1. Stop before merging `develop` into `main`.
2. Prepare a concise evidence-backed development summary for the GitHub blog.
3. Let the project owner publish or approve the Build the Lab entry.
4. Merge `develop` into `main` only after that checkpoint is acknowledged.
5. Confirm release CI, then create the `v1.0.0` tag.

This policy makes the blog checkpoint visible before the history-changing release
merge instead of trying to reconstruct the development story afterward.

For v1.0.0, all five steps completed successfully. Active development now targets
v1.1, beginning with matched serial/4/8-worker real-PySDM server benchmarks.
