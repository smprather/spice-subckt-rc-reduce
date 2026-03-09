"""SPICE .subckt file parser and writer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .value import parse_value, format_value


@dataclass
class Element:
    """A single SPICE element (R, C, or passthrough)."""
    name: str
    element_type: str  # first char uppercased: R, C, X, M, etc.
    nodes: list[str]
    value: float | None = None  # parsed value for R/C, None for others
    raw_line: str = ""  # original line(s) for passthrough elements


@dataclass
class Subcircuit:
    """A parsed .SUBCKT block."""
    name: str
    ports: list[str]
    elements: list[Element] = field(default_factory=list)
    raw_params: str = ""  # any trailing params on .SUBCKT line


@dataclass
class SpiceFile:
    """A complete SPICE file with subcircuits and top-level content."""
    subcircuits: list[Subcircuit] = field(default_factory=list)
    header_lines: list[str] = field(default_factory=list)
    trailer_lines: list[str] = field(default_factory=list)


def _join_continuation_lines(lines: list[str]) -> list[str]:
    """Join continuation lines (starting with +) to previous line."""
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("+") and result:
            result[-1] = result[-1] + " " + stripped[1:].strip()
        else:
            result.append(line)
    return result


def _parse_element(line: str) -> Element:
    """Parse a single element line into an Element."""
    stripped = line.strip()
    if not stripped:
        return Element(name="", element_type="", nodes=[], raw_line=line)

    tokens = stripped.split()
    name = tokens[0]
    etype = name[0].upper()

    if etype in ("R", "C") and len(tokens) >= 4:
        node_a = tokens[1]
        node_b = tokens[2]
        value_str = tokens[3]
        try:
            value = parse_value(value_str)
        except ValueError:
            # Can't parse value — treat as passthrough
            return Element(
                name=name, element_type=etype, nodes=[node_a, node_b],
                raw_line=stripped,
            )
        return Element(
            name=name, element_type=etype, nodes=[node_a, node_b],
            value=value, raw_line=stripped,
        )
    else:
        # Passthrough: extract nodes heuristically but keep raw line
        return Element(
            name=name, element_type=etype, nodes=tokens[1:],
            raw_line=stripped,
        )


def parse_file(path: str | Path) -> SpiceFile:
    """Parse a SPICE file containing .subckt definitions."""
    path = Path(path)
    raw_lines = path.read_text().splitlines()
    lines = _join_continuation_lines(raw_lines)

    spice_file = SpiceFile()
    current_subckt: Subcircuit | None = None
    in_subckt = False

    for line in lines:
        stripped = line.strip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("*"):
            if not in_subckt:
                if not spice_file.subcircuits:
                    spice_file.header_lines.append(line)
                else:
                    spice_file.trailer_lines.append(line)
            continue

        upper = stripped.upper()

        # .SUBCKT line
        if upper.startswith(".SUBCKT"):
            tokens = stripped.split()
            # .SUBCKT name port1 port2 ... [params]
            name = tokens[1]
            # Find where ports end (ports are non-keyword tokens)
            ports = []
            raw_params = ""
            for i, tok in enumerate(tokens[2:], start=2):
                if "=" in tok:
                    raw_params = " ".join(tokens[i:])
                    break
                ports.append(tok)
            current_subckt = Subcircuit(name=name, ports=ports, raw_params=raw_params)
            in_subckt = True
            continue

        # .ENDS line
        if upper.startswith(".ENDS"):
            if current_subckt is not None:
                spice_file.subcircuits.append(current_subckt)
                current_subckt = None
            in_subckt = False
            continue

        # Element line inside subcircuit
        if in_subckt and current_subckt is not None:
            elem = _parse_element(stripped)
            current_subckt.elements.append(elem)
        else:
            if not spice_file.subcircuits:
                spice_file.header_lines.append(line)
            else:
                spice_file.trailer_lines.append(line)

    return spice_file


def write_file(spice_file: SpiceFile, path: str | Path) -> None:
    """Write a SpiceFile back to disk."""
    path = Path(path)
    lines: list[str] = []

    for hl in spice_file.header_lines:
        lines.append(hl)

    for subckt in spice_file.subcircuits:
        parts = [".SUBCKT", subckt.name] + subckt.ports
        if subckt.raw_params:
            parts.append(subckt.raw_params)
        lines.append(" ".join(parts))

        for elem in subckt.elements:
            if elem.element_type in ("R", "C") and elem.value is not None:
                lines.append(
                    f"{elem.name} {elem.nodes[0]} {elem.nodes[1]} {format_value(elem.value)}"
                )
            else:
                lines.append(elem.raw_line)

        lines.append(f".ENDS {subckt.name}")

    for tl in spice_file.trailer_lines:
        lines.append(tl)

    path.write_text("\n".join(lines) + "\n")
