# pbg-ketchup

A [process-bigraph](https://github.com/vivarium-collective/process-bigraph)
wrapper for **[KETCHUP](https://github.com/maranasgroup/KETCHUP)** (Maranas
group) — kinetic parameter estimation for metabolic networks.

KETCHUP fits the kinetic parameters of a metabolic network by solving a single
nonlinear program with **IPOPT** so that the model recapitulates measured
steady-state fluxes and metabolite concentrations across wild-type and
perturbed conditions. This package bridges the **real** `ktools` solver as a
process-bigraph `Step` — `update()` builds the genuine Pyomo model and calls
IPOPT. Nothing is reimplemented or mocked.

Two K-FIT *E. coli* models are bundled and ready to fit out of the box:
`k-ecoli74` (74-reaction core metabolism) and `k-ecoli307` (307 reactions,
~2,500 rate constants).

## Why a `Step` (not a `Process`)?

Parameter estimation is a one-shot solve, not a time-stepped integration. A
process-bigraph `Step` fires when its inputs change, so the wrapper exposes a
`seed` **input port**: an upstream sweep or controller can write successive
seeds to drive **multistart** estimation, and each new seed re-triggers the fit.

## Installation

KETCHUP depends on the **IPOPT** solver, which is a compiled binary. The two
supported ways to provide it:

```bash
# Option A — conda (matches upstream KETCHUP, recommended):
mamba env create -f third_party/ketchup_pbg_environment.yml
mamba activate pbg-ketchup
pip install -e .            # add this wrapper into the env

# Option B — uv venv + a precompiled IPOPT from IDAES:
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]" idaes-pse
idaes get-extensions       # downloads an ipopt binary onto PATH
```

`ktools` itself ships no PyPI release, so its source is **vendored** under
`third_party/ktools/` (offline-reproducible). If that copy is ever removed,
`pbg_ketchup.runtime.ensure_ketchup()` falls back to cloning upstream into a
cache dir.

> Once installed, the `KetchupEstimator` process registers automatically via
> `bigraph_schema.package.discover` — no manual `register_link()` is needed.

## Quick start

```python
import os
from process_bigraph import allocate_core
from pbg_ketchup import KetchupEstimator

step = KetchupEstimator(config={"model_name": "k-ecoli74"}, core=allocate_core())
result = step.update({"seed": 0})

print(result["status"])         # IPOPT termination condition
print(result["sse"])            # objective: total sum-of-squared residuals
print(len(result["kf"]))        # estimated forward rate constants
print(result["fluxes"]["R1"])   # fitted reaction rate
```

For a fast, bounded run pass an IPOPT options file capping iterations:

```python
open("fast.opt", "w").write("max_iter 200\nmax_cpu_time 30\n")
step = KetchupEstimator(
    config={"model_name": "k-ecoli307", "solver_options": "fast.opt"},
    core=allocate_core(),
)
```

## API reference

### `KetchupEstimator(Step)`

| Port | Dir | Schema | Meaning |
|---|---|---|---|
| `seed` | in | `integer` | RNG seed for IPOPT initialisation (drivable for multistart) |
| `kf`, `kr` | out | `map[string,float]` | Estimated forward / reverse elementary-step rate constants |
| `concentrations` | out | `map[string,float]` | Fitted metabolite concentrations (experiment 0) |
| `enzymes` | out | `map[string,float]` | Fitted enzyme levels (experiment 0) |
| `fluxes` | out | `map[string,float]` | Fitted reaction rates (experiment 0) |
| `sse` | out | `float` | Total sum-of-squared residuals (objective) |
| `status` | out | `string` | IPOPT termination condition |
| `solve_time` | out | `float` | Wall-clock seconds for generate + solve |
| `n_parameters` | out | `integer` | `len(kf) + len(kr)` |
| `stability` | out | `string` | `stable` / `unstable` / `not_evaluated` (Jacobian eigen-check; opt-in via `compute_stability`) |

Key config: `model_name` (`k-ecoli74` / `k-ecoli307`), explicit
`directory_model` / `filename_*` overrides for your own K-FIT models,
`solver_options` (IPOPT options-file path), `output_dir`, `compute_stability`.

### Composite generators (dashboard-visible)

- `ketchup_baseline(model_name, seed, solver_options, output_dir)` — fit one model.
- `ketchup_multistart(model_name, seed, ...)` — re-fit from an alternate seed.

## Architecture mapping

| KETCHUP / `ktools` | pbg-ketchup |
|---|---|
| `ketchup_generate_model(options)` | built inside `update()` |
| `solve_ketchup_model(model, options)` (IPOPT) | called inside `update()` |
| solved Pyomo vars `kf/kr/c/e/rate/error` | read out to output ports |
| K-FIT `*_model/_mechanism/_data.xlsx` | `datasets/<model>/`, resolved by `runtime` |
| `ipopt.opt` solver options | `third_party/ipopt.opt` (or per-run override) |

## Demo

```bash
python demo/demo_report.py   # runs both models + a multistart, writes demo/report.html
```

The report runs the **real** IPOPT solver on `k-ecoli74` and `k-ecoli307`
(bounded for speed), parses IPOPT's own iteration log into a convergence trace,
and renders interactive Plotly charts, a `bigraph-viz2` architecture diagram, and
a collapsible result-document tree. It opens in your browser automatically.

## Limitations & assumptions

- **Bounded demo solves.** The demo caps `max_iter`/`max_cpu_time`, so reported
  solutions are genuine but *partial* (the IPOPT termination condition is shown
  honestly). Remove the bound for full convergence.
- **IPOPT required.** No solver → no fit. Tests that need it `skip` rather than
  fail when IPOPT is absent.
- Only `static` (steady-state) K-FIT estimation is wired; KETCHUP also supports
  dynamic/time-series fits (`KETCHUP_dynamic.py`) not yet exposed here.
- Output maps surface the **first** experiment block; full per-experiment detail
  remains available on the underlying Pyomo model.

## Provenance

Bundles a vendored copy of `ktools` and the `k-ecoli74` / `k-ecoli307` K-FIT
datasets from <https://github.com/maranasgroup/KETCHUP> for reproducibility.
KETCHUP is the work of the Maranas group; cite their publications when using it.
