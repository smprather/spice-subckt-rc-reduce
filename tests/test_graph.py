"""Tests for RC graph representation."""

import pytest
from pathlib import Path
from rcreduce.parser import parse_file
from rcreduce.graph import RCGraph, RCElement, from_subcircuit, to_subcircuit

TESTDATA = Path(__file__).parent.parent / "testdata"


class TestRCGraph:
    def test_add_element(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        assert "a" in g.nodes
        assert "n1" in g.nodes
        assert "R1" in g.elements
        assert "R1" in g.adjacency["a"]
        assert "R1" in g.adjacency["n1"]

    def test_remove_element(self):
        g = RCGraph()
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.remove_element("R1")
        assert "R1" not in g.elements
        assert "R1" not in g.adjacency["a"]

    def test_neighbors(self):
        g = RCGraph()
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("R2", "R", 200.0, "a", "c"))
        assert g.neighbors("a") == {"b", "c"}

    def test_degree(self):
        g = RCGraph()
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("C1", "C", 1e-12, "a", "0"))
        assert g.degree("a") == 2

    def test_is_internal(self):
        g = RCGraph(port_nodes=["port1"])
        g.add_element(RCElement("R1", "R", 100.0, "port1", "n1"))
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        assert not g.is_internal("port1")
        assert not g.is_internal("0")  # ground
        assert g.is_internal("n1")

    def test_elements_between(self):
        g = RCGraph()
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("R2", "R", 200.0, "a", "b"))
        g.add_element(RCElement("R3", "R", 300.0, "a", "c"))
        between = g.elements_between("a", "b")
        assert len(between) == 2

    def test_total_capacitance(self):
        g = RCGraph()
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        g.add_element(RCElement("C2", "C", 2e-12, "n1", "0"))
        assert g.total_capacitance_at("n1") == pytest.approx(3e-12)

    def test_ground_detection(self):
        g = RCGraph()
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        g.add_element(RCElement("C2", "C", 1e-12, "n2", "GND"))
        assert "0" in g.ground_nodes
        assert "GND" in g.ground_nodes

    def test_new_name(self):
        g = RCGraph()
        n1 = g.new_name("R")
        n2 = g.new_name("R")
        assert n1 != n2
        assert n1.startswith("Rred_")


class TestFromSubcircuit:
    def test_simple_rc_chain(self):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        g = from_subcircuit(sf.subcircuits[0])
        assert "port1" in g.port_nodes
        assert "port2" in g.port_nodes
        assert len(g.elements) == 5
        assert g.is_internal("n1")
        assert g.is_internal("n2")

    def test_passthrough_preserved(self):
        sf = parse_file(TESTDATA / "passthrough.subckt")
        g = from_subcircuit(sf.subcircuits[0])
        # M and X elements should be passthrough
        assert len(g.passthrough_elements) == 3  # M1, M2, Xbuf
        assert len(g.elements) == 4  # R1, C1, R2, C2


class TestToSubcircuit:
    def test_roundtrip(self):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        original = sf.subcircuits[0]
        g = from_subcircuit(original)
        result = to_subcircuit(g, original)
        assert result.name == original.name
        assert result.ports == original.ports
        assert len(result.elements) == len(original.elements)
