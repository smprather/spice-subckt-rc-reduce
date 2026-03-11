# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RC reduction tool for SPICE subcircuit (`.subckt`) models. Parses parasitic RC networks from IC layout extraction (PEX), reduces them using TICER or merge algorithms, and outputs simplified `.subckt` files.

## Development Environment

- Python 3.14 (managed via `.python-version`)
- Package management: [uv](https://docs.astral.sh/uv/) (uses `pyproject.toml`)
- Build system: hatchling
- Dev dependency: pytest

## Commands

- **Run:** `uv run spice_subckt_rc_reduce <args>`
- **Test:** `uv run pytest`
- **Add dependency:** `uv add <package>`
- **Sync environment:** `uv sync`

## Architecture

- `main.py` — CLI entry point (argparse), registered as `spice_subckt_rc_reduce` console script
- `rcreduce/value.py` — SPICE engineering notation parser/formatter
- `rcreduce/parser.py` — `.subckt` file parsing and writing
- `rcreduce/graph.py` — RC network graph representation
- `rcreduce/ticer.py` — TICER reduction algorithm
- `rcreduce/merge.py` — Simple node-merging reduction

## Domain Context

SPICE subcircuit models (`.subckt`) define circuit components with resistor-capacitor (RC) networks. RC reduction simplifies these networks while preserving electrical behavior, reducing simulation time.

### Element formats

Resistors and capacitors may use either simple or model/param format:
- `R1 n1 n2 100`
- `R6 n1 n2 res_mod R=1125.3 TC1=0.0001 TC2=0.0000006`

Temperature coefficients (TC1, TC2, etc.) are weighted-averaged when merging resistors.

### Node protection

Nodes are protected from elimination if they are:
1. Subcircuit ports (from `.SUBCKT` line)
2. Ground/power nets (configurable via `--ground`)
3. Connected to any non-R/C element (M, X, Q, D, etc.)

In real PEX netlists, MOSFETs are typically X instances (subcircuit wrappers from foundry models), not raw M elements. The parser handles X instances by discarding params and the subcircuit name, treating the remaining tokens as net nodes.

## Workflow

- Keep `README.md` in sync with any changes to configuration, CLI options, usage, or behavior.
