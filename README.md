# spice-subckt-rc-reduce

RC reduction tool for SPICE subcircuit (`.subckt`) models. Simplifies parasitic RC networks while preserving electrical behavior at port nodes, reducing simulation time.

## Installation

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
```

## Usage

```
uv run spice_subckt_rc_reduce input.subckt -o output.subckt [options]
```

### Options

| Option | Description | Default |
|---|---|---|
| `-o, --output` | Output file (required) | — |
| `-a, --algorithm` | `ticer` or `merge` | `ticer` |
| `--tau` | TICER: time constant threshold | `1e-12` |
| `--max-fill` | TICER: max fill-in edges per elimination | `6` |
| `--r-threshold` | Merge: small resistor merge threshold | `0` (disabled) |
| `--ground NET ...` | Ground/power net names to protect from elimination | `0 GND gnd VSS vss ...` |
| `--subckt` | Target a specific subcircuit by name | all |
| `-v, --verbose` | Print reduction statistics | off |

### Examples

TICER reduction with 1ns threshold:

```
uv run spice_subckt_rc_reduce input.subckt -o reduced.subckt -a ticer --tau 1e-9 -v
```

Merge-based reduction with small resistor elimination:

```
uv run spice_subckt_rc_reduce input.subckt -o reduced.subckt -a merge --r-threshold 0.1 -v
```

Custom ground/power/bulk nets (replaces defaults):

```
uv run spice_subckt_rc_reduce input.subckt -o reduced.subckt --ground 0 VDD VSS VBP VBN
```

## Algorithms

**TICER** — Eliminates internal nodes ordered by time constant (τ = R_eff × C_node). Nodes with τ below the threshold are removed via series combination (degree 2), Y-to-Δ transform (degree 3), or star-to-mesh (degree ≥ 4). Capacitance is redistributed to neighbors proportional to conductance.

**Merge** — Iteratively applies five rules to fixed-point: parallel R merge, parallel C merge, series R merge, series C merge, and small R node collapse.

## Development

```
uv sync
uv run pytest
```
