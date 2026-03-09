# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RC reduction tool for SPICE subcircuit (.subckt) models. Early-stage Python project.

## Development Environment

- Python 3.14 (managed via `.python-version`)
- Package management: [uv](https://docs.astral.sh/uv/) (uses `pyproject.toml`)
- No dependencies yet

## Commands

- **Run:** `uv run main.py`
- **Add dependency:** `uv add <package>`
- **Sync environment:** `uv sync`

## Architecture

Single entry point at `spice_subckt_rc_reduce`.

## Domain Context

SPICE subcircuit models (`.subckt`) define circuit components with resistor-capacitor (RC) networks. RC reduction simplifies these networks while preserving electrical behavior, reducing simulation time.

## Workflow

- Keep `README.md` in sync with any changes to configuration, CLI options, usage, or behavior.
