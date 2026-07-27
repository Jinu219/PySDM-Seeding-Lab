# Lab Server Deployment

PySDM Seeding Lab can run as a persistent Streamlit service on a Linux lab
server. Long simulations can be submitted as detached background jobs, and
parameter-sweep cases can use a bounded process pool.

## 1. Install once on the server

```bash
git clone <repository-url> PySDM-Seeding-Lab
cd PySDM-Seeding-Lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-pysdm.txt
```

If the repository and environment already exist, activate that environment and
install only changed requirements.

## 2. Start the web app with nohup

```bash
bash scripts/server_web.sh start
bash scripts/server_web.sh status
```

The script stores its PID and log under `.runtime/server/`. It defaults to
`127.0.0.1:8501`, enables Streamlit headless mode, and enables detached-job mode
by default in the Run page.

To use a specific interpreter or port:

```bash
PYSDM_PYTHON=/opt/conda/envs/pysdm/bin/python \
PYSDM_SERVER_PORT=8510 \
bash scripts/server_web.sh start
```

Stop or restart only the web service with:

```bash
bash scripts/server_web.sh stop
bash scripts/server_web.sh restart
```

Detached simulation jobs are separate processes. Stopping Streamlit does not
cancel jobs that were already submitted.

### Offline GitHub deployment through cloud0

When a compute server cannot resolve or reach GitHub, deploy a committed local
branch from a Windows workstation with:

```powershell
.\scripts\deploy_server.cmd cloud7
```

The command creates a temporary Git bundle, uploads it through cloud0, copies it
to the selected compute server, fast-forwards the matching branch, restarts
Streamlit, and verifies the local health endpoint. The cloud0 password may be
requested once for `scp` and once for `ssh`.

Only committed changes are bundled. The server's mutable
`configs/default.yaml` is preserved; other tracked server-side changes stop the
deployment instead of being overwritten. To inspect the local preparation
without connecting:

```powershell
.\scripts\deploy_server.cmd cloud7 -DryRun
```

## 3. Connect safely from a workstation

Keep the default loopback binding and create an SSH tunnel from the workstation:

```bash
ssh -N -L 8501:127.0.0.1:8501 USER@LAB_SERVER
```

Then open `http://localhost:8501`. This avoids exposing an unauthenticated
Streamlit port to the wider network.

On a trusted, firewall-restricted lab LAN, direct listening is possible:

```bash
PYSDM_SERVER_HOST=0.0.0.0 bash scripts/server_web.sh start
```

Direct binding should not be used on a public interface unless an authenticated
reverse proxy and appropriate firewall rules are in place.

## 4. Submit a durable calculation

1. Open **06. Run Simulation**.
2. Select the saved scenario.
3. Leave **Run as a detached background job** enabled.
4. Select **Submit Background Job**.
5. Monitor PID, progress, result directory, and worker log in **08. Server Jobs**.

Each job stores an immutable config snapshot and status under `.runtime/jobs/`.
The worker writes scientific outputs to the configured `output.base_dir`, usually
`results/`. A browser disconnect or Streamlit page refresh does not terminate it.

The selected active job can also be controlled from **08. Server Jobs**:

- **Pause job** suspends the isolated process group. CPU use stops while the
  in-memory calculation state remains allocated.
- **Resume job** continues a paused job from that in-memory state.
- **Cancel job** sends a termination signal after explicit confirmation. It
  cannot be resumed, although partial artifacts already written to disk remain.

These controls are available on Linux servers. If a job was paused directly from
the shell with `kill -STOP -- -PID`, the page detects the process state and
enables **Resume job**. A paused job does not survive a server reboot because its
continuation state exists in memory.

## 5. Use multiple CPU cores

Set **Maximum parallel sweep workers** on **05. Parameter Sweep** and save the
scenario. Parallelism is applied to independent sweep cases. Ensemble members
inside each case remain sequential to prevent nested oversubscription.

The effective count is:

```text
min(execution.max_workers, number of sweep cases)
```

For example, the 10-case marine OFAT showcase can use at most 10 simultaneous
case workers, even if the server has 20 cores. A larger sweep can use up to 20
when `execution.max_workers: 20` is selected.

Start conservatively because memory, not CPU count, is usually the limiting
resource for real PySDM runs. The latest project benchmark measured roughly
1.03 GiB peak RSS for one isolated PySDM child in its tested profile. As a
planning estimate:

| Workers | Minimum planning RAM for workers | Practical starting point |
|---:|---:|---|
| 4 | about 4–6 GiB | first server test |
| 8 | about 8–12 GiB | after checking peak RSS |
| 10 | about 10–15 GiB | full 10-case OFAT concurrency |
| 20 | above 20 GiB plus OS/app overhead | only on a sufficiently large server |

Actual memory depends on timestep, super-droplet counts, diagnostics, and the
ensemble backend. Check `htop`, `free -h`, and the generated resource evidence
before increasing the worker count.

## 6. Recommended first server test

Use `marine_showcase_ofat_v1` with:

```yaml
execution:
  max_workers: 4
```

Submit it as a background job. After all 10 cases succeed, compare wall time and
peak memory, then increase to 8 or 10 workers if the server has enough headroom.
Using 20 workers for this particular scenario gives no additional concurrency
because it contains only 10 cases.

For the controlled v1.1 qualification, do not edit and submit three scenarios
manually. Use the matched dry-run-first benchmark runner documented in
[`WORKER_SCALING_BENCHMARK.md`](WORKER_SCALING_BENCHMARK.md). It changes only
`execution.max_workers`, captures the machine and Git scope, samples the complete
live process tree, and preserves failed-trial evidence.

## 7. First real-PySDM web pilot

Before the full scaling qualification, use the saved
`Lab Server Real PySDM Pilot v1` scenario from **06. Run Simulation**. Select the
scenario directly rather than applying it to `configs/default.yaml`, verify
`4` sweep cases, `2` ensemble members, `16` total model runs, `4/4` case workers,
and zero validation errors, then submit it as a detached background job.

Monitor it from **08. Server Jobs** and inspect the completed result from
**07. Results**. This pilot checks the real adapter, process pool, durable job,
diagnostic, and reporting workflow. Its small-ensemble differences are descriptive
and do not support a cloud-seeding efficacy claim.

## 8. Lab-meeting growth-pathway run

After the pilot, select `Lab Meeting Growth Pathway v1` on **06. Run
Simulation**. Verify `6` sweep cases, `5` ensemble members, `60` total model
runs, `6/6` case workers, and zero blocking errors. Run it only from a commit
containing the paired-control seed-capacity fix; older pilot results that diverge
before injection are not valid seeding-response figures.

The presentation workflow and plot-reading order are documented in
[`LAB_MEETING_GROWTH_PATHWAY_KO.md`](LAB_MEETING_GROWTH_PATHWAY_KO.md).
