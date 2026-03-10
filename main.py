"""CLI entry point for RC reduction tool."""

import argparse
import sys

from rcreduce.parser import parse_file, write_file
from rcreduce.graph import DEFAULT_GROUND_NAMES, from_subcircuit, to_subcircuit
from rcreduce.ticer import reduce_ticer
from rcreduce.merge import reduce_merge


def main():
    parser = argparse.ArgumentParser(
        description="RC reduction tool for SPICE .subckt files"
    )
    parser.add_argument("input", help="Input .subckt file")
    parser.add_argument("-o", "--output", required=True, help="Output .subckt file")
    parser.add_argument(
        "-a", "--algorithm", choices=["ticer", "merge"], default="ticer",
        help="Reduction algorithm (default: ticer)",
    )
    parser.add_argument(
        "--tau", type=float, default=1e-12,
        help="TICER: time constant threshold (default: 1e-12)",
    )
    parser.add_argument(
        "--max-fill", type=int, default=6,
        help="TICER: max fill-in edges per elimination (default: 6)",
    )
    parser.add_argument(
        "--r-threshold", type=float, default=0.0,
        help="Merge: small resistor threshold (default: 0, disabled)",
    )
    parser.add_argument(
        "--subckt", default=None,
        help="Target specific subcircuit by name",
    )
    parser.add_argument(
        "--ground", nargs="*", default=None, metavar="NET",
        help="Ground/power net names to protect from elimination "
        f"(default: {' '.join(sorted(DEFAULT_GROUND_NAMES))})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print reduction statistics",
    )

    args = parser.parse_args()

    ground_names = set(args.ground) if args.ground is not None else None

    spice_file = parse_file(args.input)

    if not spice_file.subcircuits:
        print("No subcircuits found in input file.", file=sys.stderr)
        sys.exit(1)

    for subckt in spice_file.subcircuits:
        if args.subckt and subckt.name != args.subckt:
            continue

        graph = from_subcircuit(subckt, ground_names=ground_names)
        n_nodes_before = len(graph.nodes)
        n_elems_before = len(graph.elements)

        if args.algorithm == "ticer":
            reduce_ticer(graph, tau_threshold=args.tau, max_fill=args.max_fill)
        else:
            reduce_merge(graph, r_threshold=args.r_threshold)

        n_nodes_after = len(graph.nodes)
        n_elems_after = len(graph.elements)

        if args.verbose:
            print(f"Subcircuit: {subckt.name}")
            print(f"  Nodes:    {n_nodes_before} -> {n_nodes_after}")
            print(f"  Elements: {n_elems_before} -> {n_elems_after}")

        # Replace subcircuit in-place
        reduced = to_subcircuit(graph, subckt)
        subckt.elements = reduced.elements

    write_file(spice_file, args.output)

    if args.verbose:
        print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()
