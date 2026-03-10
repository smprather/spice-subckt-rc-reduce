"""RC network graph representation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .parser import Subcircuit, Element

DEFAULT_GROUND_NAMES = frozenset({"0", "GND", "gnd", "Gnd", "VSS", "vss", "Vss"})


@dataclass
class RCElement:
    """A resistor or capacitor in the RC graph."""
    name: str
    etype: str  # "R" or "C"
    value: float
    node_a: str
    node_b: str
    model: str = ""
    params: dict[str, str] = field(default_factory=dict)


class RCGraph:
    """Adjacency-based RC multigraph."""

    def __init__(
        self,
        port_nodes: list[str] | None = None,
        ground_names: set[str] | None = None,
    ):
        self.nodes: set[str] = set()
        self.port_nodes: set[str] = set(port_nodes or [])
        self._ground_names: set[str] = (
            ground_names if ground_names is not None else set(DEFAULT_GROUND_NAMES)
        )
        self.ground_nodes: set[str] = set()
        self.elements: dict[str, RCElement] = {}  # name -> element
        self.adjacency: dict[str, set[str]] = {}  # node -> set of element names
        self.passthrough_elements: list[Element] = []
        self._name_counter: int = 0

    def _ensure_node(self, node: str) -> None:
        if node not in self.nodes:
            self.nodes.add(node)
            self.adjacency[node] = set()
            if node in self._ground_names:
                self.ground_nodes.add(node)

    def add_element(self, elem: RCElement) -> None:
        self._ensure_node(elem.node_a)
        self._ensure_node(elem.node_b)
        self.elements[elem.name] = elem
        self.adjacency[elem.node_a].add(elem.name)
        self.adjacency[elem.node_b].add(elem.name)

    def remove_element(self, name: str) -> None:
        elem = self.elements.pop(name)
        self.adjacency[elem.node_a].discard(name)
        self.adjacency[elem.node_b].discard(name)

    def remove_node(self, node: str) -> None:
        # Remove all elements attached to this node first
        for ename in list(self.adjacency.get(node, [])):
            if ename in self.elements:
                self.remove_element(ename)
        self.nodes.discard(node)
        self.adjacency.pop(node, None)
        self.port_nodes.discard(node)
        self.ground_nodes.discard(node)

    def neighbors(self, node: str) -> set[str]:
        """Return set of nodes adjacent to the given node."""
        result: set[str] = set()
        for ename in self.adjacency.get(node, []):
            elem = self.elements.get(ename)
            if elem is None:
                continue
            other = elem.node_b if elem.node_a == node else elem.node_a
            result.add(other)
        return result

    def degree(self, node: str) -> int:
        """Number of elements attached to node."""
        return len(self.adjacency.get(node, set()))

    def elements_at(self, node: str) -> list[RCElement]:
        """All elements connected to a node."""
        return [
            self.elements[n]
            for n in self.adjacency.get(node, [])
            if n in self.elements
        ]

    def resistors_at(self, node: str) -> list[RCElement]:
        return [e for e in self.elements_at(node) if e.etype == "R"]

    def capacitors_at(self, node: str) -> list[RCElement]:
        return [e for e in self.elements_at(node) if e.etype == "C"]

    def total_capacitance_at(self, node: str) -> float:
        return sum(e.value for e in self.capacitors_at(node))

    def is_internal(self, node: str) -> bool:
        """A node is internal if it's not a port node or ground node."""
        return node not in self.port_nodes and node not in self.ground_nodes

    def new_name(self, prefix: str) -> str:
        """Generate a unique element name."""
        self._name_counter += 1
        name = f"{prefix}red_{self._name_counter:04d}"
        while name in self.elements:
            self._name_counter += 1
            name = f"{prefix}red_{self._name_counter:04d}"
        return name

    def elements_between(self, node_a: str, node_b: str) -> list[RCElement]:
        """All elements connecting two specific nodes."""
        result = []
        for ename in self.adjacency.get(node_a, []):
            elem = self.elements.get(ename)
            if elem is None:
                continue
            if (elem.node_a == node_a and elem.node_b == node_b) or \
               (elem.node_a == node_b and elem.node_b == node_a):
                result.append(elem)
        return result


def merge_params(elements: list[RCElement], weights: list[float]) -> tuple[str, dict[str, str]]:
    """Compute weighted-average params and pick model from merged elements.

    Returns (model, params) where params values are formatted as strings.
    For series R: weight by resistance. For parallel R: weight by conductance.
    """
    # Model: use the common model if all agree, otherwise drop it
    models = {e.model for e in elements if e.model}
    model = models.pop() if len(models) == 1 else ""

    # Collect all param keys
    all_keys: set[str] = set()
    for e in elements:
        all_keys.update(e.params.keys())

    if not all_keys:
        return model, {}

    w_total = sum(weights)
    if w_total <= 0:
        return model, {}

    params: dict[str, str] = {}
    for key in sorted(all_keys):
        weighted_sum = 0.0
        for e, w in zip(elements, weights):
            val_str = e.params.get(key)
            if val_str is not None:
                try:
                    weighted_sum += float(val_str) * w
                except ValueError:
                    break
            # Elements missing a param contribute 0 (implicit default)
        else:
            avg = weighted_sum / w_total
            params[key] = f"{avg:.6g}"

    return model, params


def from_subcircuit(
    subckt: Subcircuit, ground_names: set[str] | None = None,
) -> RCGraph:
    """Build an RCGraph from a parsed Subcircuit."""
    graph = RCGraph(port_nodes=subckt.ports, ground_names=ground_names)
    # Ensure all port nodes exist in the graph even if no R/C connects to them
    for port in subckt.ports:
        graph._ensure_node(port)
    for elem in subckt.elements:
        if elem.element_type in ("R", "C") and elem.value is not None:
            rc = RCElement(
                name=elem.name,
                etype=elem.element_type,
                value=elem.value,
                node_a=elem.nodes[0],
                node_b=elem.nodes[1],
                model=elem.model,
                params=dict(elem.params),
            )
            graph.add_element(rc)
        else:
            graph.passthrough_elements.append(elem)
    return graph


def to_subcircuit(graph: RCGraph, original: Subcircuit) -> Subcircuit:
    """Convert an RCGraph back into a Subcircuit."""
    elements: list[Element] = []

    # Add R/C elements sorted by name for deterministic output
    for name in sorted(graph.elements):
        rc = graph.elements[name]
        elements.append(Element(
            name=rc.name,
            element_type=rc.etype,
            nodes=[rc.node_a, rc.node_b],
            value=rc.value,
            model=rc.model,
            params=dict(rc.params),
        ))

    # Add passthrough elements
    elements.extend(graph.passthrough_elements)

    return Subcircuit(
        name=original.name,
        ports=original.ports,
        elements=elements,
        raw_params=original.raw_params,
    )
