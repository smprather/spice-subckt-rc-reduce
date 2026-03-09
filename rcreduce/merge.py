"""Simple node-merging RC reduction."""

from __future__ import annotations

from .graph import RCGraph, RCElement


def _merge_parallel_resistors(graph: RCGraph) -> bool:
    """Merge parallel resistors between the same node pair."""
    changed = False
    visited: set[tuple[str, str]] = set()

    for node in list(graph.nodes):
        for neighbor in graph.neighbors(node):
            pair = (min(node, neighbor), max(node, neighbor))
            if pair in visited:
                continue
            visited.add(pair)

            resistors = [
                e for e in graph.elements_between(node, neighbor) if e.etype == "R"
            ]
            if len(resistors) < 2:
                continue

            # Parallel: 1/R = sum(1/Ri)
            conductance = sum(1.0 / r.value for r in resistors if r.value > 0)
            if conductance <= 0:
                continue
            new_value = 1.0 / conductance

            # Remove all, add one
            for r in resistors:
                graph.remove_element(r.name)
            new_name = graph.new_name("R")
            graph.add_element(RCElement(new_name, "R", new_value, pair[0], pair[1]))
            changed = True

    return changed


def _merge_parallel_capacitors(graph: RCGraph) -> bool:
    """Merge parallel capacitors between the same node pair."""
    changed = False
    visited: set[tuple[str, str]] = set()

    for node in list(graph.nodes):
        for neighbor in graph.neighbors(node):
            pair = (min(node, neighbor), max(node, neighbor))
            if pair in visited:
                continue
            visited.add(pair)

            caps = [
                e for e in graph.elements_between(node, neighbor) if e.etype == "C"
            ]
            if len(caps) < 2:
                continue

            new_value = sum(c.value for c in caps)

            for c in caps:
                graph.remove_element(c.name)
            new_name = graph.new_name("C")
            graph.add_element(RCElement(new_name, "C", new_value, pair[0], pair[1]))
            changed = True

    return changed


def _merge_series_resistors(graph: RCGraph) -> bool:
    """Merge series resistors through degree-2 internal nodes."""
    changed = False

    for node in list(graph.nodes):
        if node not in graph.nodes:
            continue
        if not graph.is_internal(node):
            continue

        elems = graph.elements_at(node)
        if len(elems) != 2:
            continue

        # Both must be resistors
        if not all(e.etype == "R" for e in elems):
            continue

        r1, r2 = elems
        # Find the other endpoints
        other1 = r1.node_b if r1.node_a == node else r1.node_a
        other2 = r2.node_b if r2.node_a == node else r2.node_a

        # Don't merge if it would create a self-loop
        if other1 == other2:
            continue

        new_value = r1.value + r2.value

        graph.remove_element(r1.name)
        graph.remove_element(r2.name)
        graph.nodes.discard(node)
        graph.adjacency.pop(node, None)

        new_name = graph.new_name("R")
        graph.add_element(RCElement(new_name, "R", new_value, other1, other2))
        changed = True

    return changed


def _merge_series_capacitors(graph: RCGraph) -> bool:
    """Merge series capacitors through degree-2 internal nodes."""
    changed = False

    for node in list(graph.nodes):
        if node not in graph.nodes:
            continue
        if not graph.is_internal(node):
            continue

        elems = graph.elements_at(node)
        if len(elems) != 2:
            continue

        if not all(e.etype == "C" for e in elems):
            continue

        c1, c2 = elems
        other1 = c1.node_b if c1.node_a == node else c1.node_a
        other2 = c2.node_b if c2.node_a == node else c2.node_a

        if other1 == other2:
            continue

        # Series: 1/C = 1/C1 + 1/C2
        if c1.value <= 0 or c2.value <= 0:
            continue
        new_value = 1.0 / (1.0 / c1.value + 1.0 / c2.value)

        graph.remove_element(c1.name)
        graph.remove_element(c2.name)
        graph.nodes.discard(node)
        graph.adjacency.pop(node, None)

        new_name = graph.new_name("C")
        graph.add_element(RCElement(new_name, "C", new_value, other1, other2))
        changed = True

    return changed


def _merge_small_resistors(graph: RCGraph, r_threshold: float) -> bool:
    """Merge nodes connected by small resistors."""
    if r_threshold <= 0:
        return False

    changed = False

    for ename in list(graph.elements):
        if ename not in graph.elements:
            continue
        elem = graph.elements[ename]
        if elem.etype != "R" or elem.value >= r_threshold:
            continue

        node_a, node_b = elem.node_a, elem.node_b

        # Decide which node survives: port/ground nodes take precedence
        a_protected = not graph.is_internal(node_a)
        b_protected = not graph.is_internal(node_b)

        if a_protected and b_protected:
            # Both protected — skip
            continue

        if b_protected:
            keep, remove = node_b, node_a
        else:
            keep, remove = node_a, node_b

        # Rewire all elements from 'remove' to 'keep'
        for en in list(graph.adjacency.get(remove, [])):
            if en not in graph.elements:
                continue
            e = graph.elements[en]
            if e.node_a == remove:
                e.node_a = keep
            if e.node_b == remove:
                e.node_b = keep
            # Remove self-loops
            if e.node_a == e.node_b:
                graph.remove_element(en)
            else:
                # Update adjacency
                graph.adjacency[remove].discard(en)
                graph.adjacency[keep].add(en)

        graph.nodes.discard(remove)
        graph.adjacency.pop(remove, None)
        changed = True

    return changed


def reduce_merge(graph: RCGraph, r_threshold: float = 0.0) -> RCGraph:
    """Apply merge-based reduction rules iteratively to fixed-point."""
    while True:
        changed = False
        changed |= _merge_parallel_resistors(graph)
        changed |= _merge_parallel_capacitors(graph)
        changed |= _merge_series_resistors(graph)
        changed |= _merge_series_capacitors(graph)
        changed |= _merge_small_resistors(graph, r_threshold)
        if not changed:
            break
    return graph
