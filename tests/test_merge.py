"""Tests for merge-based reduction."""

import pytest
from rcreduce.graph import RCGraph, RCElement
from rcreduce.merge import reduce_merge


class TestParallelMerge:
    def test_parallel_resistors(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("R2", "R", 100.0, "a", "b"))
        reduce_merge(g)
        # Should merge to one resistor of 50 ohms
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(50.0)

    def test_parallel_capacitors(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("C1", "C", 1e-12, "a", "b"))
        g.add_element(RCElement("C2", "C", 2e-12, "a", "b"))
        reduce_merge(g)
        caps = [e for e in g.elements.values() if e.etype == "C"]
        assert len(caps) == 1
        assert caps[0].value == pytest.approx(3e-12)


class TestSeriesMerge:
    def test_series_resistors(self):
        # a --R1-- n1 --R2-- b
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("R2", "R", 200.0, "n1", "b"))
        reduce_merge(g)
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(300.0)
        assert "n1" not in g.nodes

    def test_series_capacitors(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("C1", "C", 2e-12, "a", "n1"))
        g.add_element(RCElement("C2", "C", 2e-12, "n1", "b"))
        reduce_merge(g)
        caps = [e for e in g.elements.values() if e.etype == "C"]
        assert len(caps) == 1
        assert caps[0].value == pytest.approx(1e-12)

    def test_no_series_merge_at_port(self):
        """Port nodes should not be eliminated."""
        g = RCGraph(port_nodes=["a", "b", "c"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("R2", "R", 200.0, "b", "c"))
        reduce_merge(g)
        # b is a port — should NOT merge
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 2

    def test_no_series_merge_mixed(self):
        """Don't merge R+C in series."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "b"))
        reduce_merge(g)
        assert len(g.elements) == 2  # no change


class TestSmallResistorMerge:
    def test_small_r_merge(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 0.01, "a", "n1"))
        g.add_element(RCElement("R2", "R", 100.0, "n1", "b"))
        reduce_merge(g, r_threshold=0.1)
        # n1 merged into a (a is port, n1 is internal)
        assert "n1" not in g.nodes
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(100.0, rel=1e-2)

    def test_no_merge_both_ports(self):
        """Don't merge small R between two port nodes."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 0.01, "a", "b"))
        reduce_merge(g, r_threshold=0.1)
        assert len(g.elements) == 1  # unchanged


class TestFixedPoint:
    def test_chain_reduces_fully(self):
        """A chain of series resistors should reduce to one."""
        g = RCGraph(port_nodes=["a", "e"])
        g.add_element(RCElement("R1", "R", 10.0, "a", "b"))
        g.add_element(RCElement("R2", "R", 20.0, "b", "c"))
        g.add_element(RCElement("R3", "R", 30.0, "c", "d"))
        g.add_element(RCElement("R4", "R", 40.0, "d", "e"))
        reduce_merge(g)
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(100.0)


class TestRCPiReduction:
    def test_rc_pi_parallel_merge(self):
        """rc_pi has parallel R and C — should merge them."""
        from pathlib import Path
        from rcreduce.parser import parse_file
        from rcreduce.graph import from_subcircuit

        sf = parse_file(Path(__file__).parent.parent / "testdata" / "rc_pi.subckt")
        g = from_subcircuit(sf.subcircuits[0])
        reduce_merge(g)
        # R1||R2 -> 500 ohms, C1||C2 -> 10P
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(500.0)
        # C1+C2 at in, C3 at out — only C1||C2 should merge
        caps = [e for e in g.elements.values() if e.etype == "C"]
        assert len(caps) == 2


class TestParamMerge:
    def test_parallel_r_conductance_weighted_params(self):
        """Parallel merge: params weighted by conductance (1/R)."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "b", "mod",
                                {"TC1": "0.001", "TC2": "0.0001"}))
        g.add_element(RCElement("R2", "R", 100.0, "a", "b", "mod",
                                {"TC1": "0.003", "TC2": "0.0001"}))
        reduce_merge(g)
        r = [e for e in g.elements.values() if e.etype == "R"]
        assert len(r) == 1
        assert r[0].model == "mod"
        # Equal R → equal conductance → simple average
        assert float(r[0].params["TC1"]) == pytest.approx(0.002)
        assert float(r[0].params["TC2"]) == pytest.approx(0.0001)

    def test_series_r_resistance_weighted_params(self):
        """Series merge: params weighted by resistance."""
        g = RCGraph(port_nodes=["a", "b"])
        # R1=100 with TC1=0.001, R2=300 with TC1=0.003
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1", "mod",
                                {"TC1": "0.001"}))
        g.add_element(RCElement("R2", "R", 300.0, "n1", "b", "mod",
                                {"TC1": "0.003"}))
        reduce_merge(g)
        r = [e for e in g.elements.values() if e.etype == "R"]
        assert len(r) == 1
        assert r[0].value == pytest.approx(400.0)
        # Weighted: (100*0.001 + 300*0.003) / 400 = (0.1 + 0.9) / 400 = 0.0025
        assert float(r[0].params["TC1"]) == pytest.approx(0.0025)

    def test_mixed_models_drops_model(self):
        """When merging elements with different models, drop the model."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "b", "mod_a",
                                {"TC1": "0.001"}))
        g.add_element(RCElement("R2", "R", 100.0, "a", "b", "mod_b",
                                {"TC1": "0.003"}))
        reduce_merge(g)
        r = [e for e in g.elements.values() if e.etype == "R"]
        assert r[0].model == ""
