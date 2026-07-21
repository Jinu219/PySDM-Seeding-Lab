# v1.0 Release Checklist

This document defines a finite finish line for v1.0. Work outside these gates is
deferred unless it is required to fix a correctness or reproducibility defect.
The machine-readable source of truth is `release/v1.0.0.json`.

## Current decision

v1.0 is **not ready to merge**. Two of five required gates are complete. The next
and only active scientific blocker is a defensible direct-temporal drizzle-onset
dataset and its parcel-time mapping. The BASTALIAS importer is useful real-data
evidence, but the moving aircraft samples changing horizontal volumes and therefore
remains a spatiotemporal proxy. The ARM ENA fixed-column importer is a closer
temporal candidate, but horizontal advection still changes the sampled parcels and
radar reflectivity is not the model-native liquid-fraction transition.

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
3. **Direct-temporal validation — blocked.** Obtain a dataset whose sampled volume,
   clock, event definition, observable mapping, and model-time alignment support a
   defensible comparison. The ARM ENA pipeline is ready for a credentialed real-file
   audit but does not by itself satisfy this gate.
4. **Scientific scope review — pending.** Retain, revise, or reject the operational
   1% transition floor and make every release claim consistent with the evidence.
5. **Release candidate — pending.** Freeze documentation, verify the end-to-end user
   workflow, pass Windows/Ubuntu CI and real PySDM integration, and close all gates.

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
