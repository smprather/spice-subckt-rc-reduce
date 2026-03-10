"""TICER RC reduction algorithm."""

from __future__ import annotations

import heapq

from .graph import RCGraph, RCElement, merge_params


def _compute_tau(graph: RCGraph, node: str) -> float:
    """Compute time constant τ = R_eff × C_node for a node."""
    resistors = graph.resistors_at(node)
    caps = graph.capacitors_at(node)

    c_node = sum(c.value for c in caps)
    if not resistors or c_node <= 0:
        return float("inf")

    g_sum = sum(1.0 / r.value for r in resistors if r.value > 0)
    if g_sum <= 0:
        return float("inf")

    r_eff = 1.0 / g_sum
    return r_eff * c_node


def _eliminate_node(graph: RCGraph, node: str, max_fill: int) -> bool:
    """Eliminate a single internal node from the graph.

    Returns True if elimination succeeded.
    """
    resistors = graph.resistors_at(node)
    caps = graph.capacitors_at(node)

    # Gather neighbor info from resistors
    neighbor_data: dict[str, float] = {}  # neighbor -> conductance
    for r in resistors:
        other = r.node_b if r.node_a == node else r.node_a
        if other == node:
            continue  # self-loop
        g = 1.0 / r.value if r.value > 0 else 0.0
        neighbor_data[other] = neighbor_data.get(other, 0.0) + g

    neighbors = list(neighbor_data.keys())
    degree = len(neighbors)

    if degree == 0:
        # Isolated node with only caps — just remove everything
        for c in caps:
            graph.remove_element(c.name)
        for r in resistors:
            if r.name in graph.elements:
                graph.remove_element(r.name)
        graph.nodes.discard(node)
        graph.adjacency.pop(node, None)
        return True

    # Check fill-in for degree >= 4
    if degree >= 4:
        # Star-to-mesh creates degree*(degree-1)/2 new edges
        new_edges = degree * (degree - 1) // 2
        if new_edges > max_fill:
            return False

    g_sum = sum(neighbor_data.values())
    if g_sum <= 0:
        return False

    # Capacitance redistribution
    c_node = sum(c.value for c in caps)
    if c_node > 0:
        for nb, g_nb in neighbor_data.items():
            c_share = c_node * (g_nb / g_sum)
            if c_share > 0:
                # Find existing cap to ground from neighbor, or add new one
                # Distribute as cap from neighbor to ground (node 0)
                # Actually, distribute to neighbor's existing ground caps
                # or create a new grounding cap
                _add_cap_to_ground(graph, nb, c_share)

    # Remove all elements at this node
    for r in resistors:
        if r.name in graph.elements:
            graph.remove_element(r.name)
    for c in caps:
        if c.name in graph.elements:
            graph.remove_element(c.name)

    # Create replacement resistors based on degree
    if degree == 1:
        # Dangling node — just remove
        pass
    elif degree == 2:
        # Series combination: R = R_a + R_b
        n1, n2 = neighbors
        r_new = 1.0 / neighbor_data[n1] + 1.0 / neighbor_data[n2]
        if r_new > 0:
            name = graph.new_name("R")
            graph.add_element(RCElement(name, "R", r_new, n1, n2))
    else:
        # General star-to-mesh (works for degree 3 Y-to-Δ and higher)
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                ni, nj = neighbors[i], neighbors[j]
                gi = neighbor_data[ni]
                gj = neighbor_data[nj]
                if gi <= 0 or gj <= 0:
                    continue
                r_new = g_sum / (gi * gj)
                if r_new > 0:
                    name = graph.new_name("R")
                    graph.add_element(RCElement(name, "R", r_new, ni, nj))

    # Combine parallel resistors created between existing node pairs
    _combine_parallel_resistors_at_neighbors(graph, neighbors)

    # Remove the eliminated node
    graph.nodes.discard(node)
    graph.adjacency.pop(node, None)
    return True


def _add_cap_to_ground(graph: RCGraph, node: str, cap_value: float) -> None:
    """Add capacitance from node to ground, merging with existing if present."""
    # Look for existing cap from node to any ground node
    for ename in list(graph.adjacency.get(node, [])):
        elem = graph.elements.get(ename)
        if elem is None or elem.etype != "C":
            continue
        other = elem.node_b if elem.node_a == node else elem.node_a
        if other in graph.ground_nodes:
            elem.value += cap_value
            return

    # No existing ground cap — create new one
    gnd = "0"
    name = graph.new_name("C")
    graph.add_element(RCElement(name, "C", cap_value, node, gnd))


def _combine_parallel_resistors_at_neighbors(
    graph: RCGraph, neighbors: list[str]
) -> None:
    """Combine parallel resistors between neighbor pairs."""
    for i in range(len(neighbors)):
        for j in range(i + 1, len(neighbors)):
            ni, nj = neighbors[i], neighbors[j]
            resistors = [
                e for e in graph.elements_between(ni, nj) if e.etype == "R"
            ]
            if len(resistors) < 2:
                continue
            g_total = sum(1.0 / r.value for r in resistors if r.value > 0)
            if g_total <= 0:
                continue
            g_weights = [1.0 / r.value for r in resistors]
            model, params = merge_params(resistors, g_weights)
            for r in resistors:
                graph.remove_element(r.name)
            name = graph.new_name("R")
            graph.add_element(RCElement(name, "R", 1.0 / g_total, ni, nj, model, params))


def reduce_ticer(
    graph: RCGraph, tau_threshold: float = 1e-12, max_fill: int = 6
) -> RCGraph:
    """Apply TICER reduction algorithm.

    Eliminates internal nodes with time constant τ < tau_threshold.
    """
    # Build initial heap
    heap: list[tuple[float, int, str]] = []  # (tau, counter, node)
    counter = 0
    node_version: dict[str, int] = {}  # for lazy deletion

    for node in graph.nodes:
        if not graph.is_internal(node):
            continue
        tau = _compute_tau(graph, node)
        node_version[node] = counter
        heapq.heappush(heap, (tau, counter, node))
        counter += 1

    while heap:
        tau, ver, node = heapq.heappop(heap)

        # Lazy deletion check
        if node not in graph.nodes:
            continue
        if node_version.get(node) != ver:
            continue
        if not graph.is_internal(node):
            continue

        if tau >= tau_threshold:
            break

        # Get neighbors before elimination
        affected = graph.neighbors(node)

        success = _eliminate_node(graph, node, max_fill)
        if not success:
            continue

        # Recompute τ for affected neighbors
        for nb in affected:
            if nb not in graph.nodes or not graph.is_internal(nb):
                continue
            new_tau = _compute_tau(graph, nb)
            node_version[nb] = counter
            heapq.heappush(heap, (new_tau, counter, nb))
            counter += 1

    return graph
