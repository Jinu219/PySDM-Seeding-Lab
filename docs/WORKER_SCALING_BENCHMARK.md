# Worker Scaling Benchmark

This is the first v1.1 qualification gate. It compares the same real-PySDM
parameter-sweep workload with 1, 4, and 8 configured case workers. It measures
performance and resource use; it does not test or establish cloud-seeding efficacy.

## What the benchmark preserves

Every trial uses the same normalized scenario, seeds, sweep cases, ensemble
settings, and physical configuration. Only `execution.max_workers` changes.
The runner executes one trial at a time and records:

- wall time, case throughput, model-run throughput, speedup, and parallel efficiency;
- sampled driver-process and complete live process-tree peak RSS;
- requested, successful, partial, and failed case counts;
- hostname, CPU count, total/available RAM, Python version, Git commit, and dirty state;
- config snapshots, child status, standard output, and standard error for each trial.

The process-tree RSS value is sampled and can miss a peak between samples. Results
therefore apply only to the measured machine, workload, commit, and sampling setup.

## 1. Prepare the server

Use an up-to-date `develop` checkout and activate the installed project environment:

```bash
git checkout develop
git pull --ff-only origin develop
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-pysdm.txt
```

Choose a stable evidence directory that identifies the server and date:

```bash
export BENCH_DIR="artifacts/worker_scaling/$(hostname)-$(date -u +%Y%m%d)"
```

## 2. Run the mandatory dry run

The default command writes a plan but performs no physical calculation:

```bash
python scripts/run_worker_scaling_benchmark.py \
  --config experiments/scenarios/marine_showcase_ofat_v1.yaml \
  --workers 1 4 8 \
  --output-dir "$BENCH_DIR"
```

Review `plan.json`. The frozen marine workload contains 10 sweep cases, three
common-seed ensemble members, and paired control/seeding calculations: 60 model
runs per trial and 180 model runs across all three trials.

The default RAM preflight budgets 1.25 GiB per effective worker plus 1 GiB reserve:

| Configured workers | Effective workers | Default planning estimate |
|---:|---:|---:|
| 1 | 1 | 2.25 GiB |
| 4 | 4 | 6.00 GiB |
| 8 | 8 | 11.00 GiB |

These are conservative planning values, not measured peaks. If the 8-worker check
fails, run `--workers 1 4` first. Do not bypass the guard unless the server operator
has independently confirmed sufficient headroom.

Physical execution also rejects a dirty Git worktree by default. This prevents
uncommitted code changes from silently mixing benchmark implementations.

## 3. Execute without depending on the SSH session

After the dry run passes, start the matched sequence with `nohup`:

```bash
nohup python scripts/run_worker_scaling_benchmark.py \
  --config experiments/scenarios/marine_showcase_ofat_v1.yaml \
  --workers 1 4 8 \
  --output-dir "$BENCH_DIR" \
  --execute \
  > "$BENCH_DIR/driver.log" 2>&1 &
echo $!
```

The trials run in the listed order, so the serial baseline completes before the
4- and 8-worker trials. The runner stops after a failed trial instead of continuing
with a more aggressive setting.

Monitor progress and available memory from another shell:

```bash
tail -f "$BENCH_DIR/driver.log"
watch -n 5 'free -h; ps -eo pid,ppid,%cpu,rss,cmd --sort=-rss | head -n 15'
```

Avoid running unrelated memory- or CPU-intensive jobs during the comparison.

## 4. Resume safely after interruption

Repeat the execution command with `--resume`. Completed successful trials are
reused only when the workload hash, hostname, Git commit, and Python version still
match. An incomplete or failed trial directory is renamed with an
`_attempt_<UTC timestamp>` suffix before retry, so its failure evidence is retained.

```bash
nohup python scripts/run_worker_scaling_benchmark.py \
  --config experiments/scenarios/marine_showcase_ofat_v1.yaml \
  --workers 1 4 8 \
  --output-dir "$BENCH_DIR" \
  --execute --resume \
  > "$BENCH_DIR/driver-resume.log" 2>&1 &
```

## 5. Return the evidence

The compact files needed for review are:

```text
plan.json
environment.json
worker_scaling.json
worker_scaling.md
workers_1/trial.json
workers_4/trial.json
workers_8/trial.json
```

If a trial failed, also return its `status.json`, `stdout.log`, and `stderr.log`.
`worker_scaling.md` identifies the fastest successful measured candidate, but that
candidate becomes a recommendation only after checking failures, memory headroom,
speedup, and parallel efficiency. It is never a universal default.
