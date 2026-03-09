"""Tests for TICER reduction algorithm."""

import pytest
from rcreduce.graph import RCGraph, RCElement
from rcreduce.ticer import reduce_ticer, _compute_tau


class TestComputeTau:
    def test_simple_tau(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        # tau = R_eff * C = 100 * 1e-12 = 1e-10
        tau = _compute_tau(g, "n1")
        assert tau == pytest.approx(1e-10)

    def test_multiple_resistors(self):
        g = RCGraph(port_nodes=["a", "b", "c"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("R2", "R", 100.0, "b", "n1"))
        g.add_element(RCElement("C1", "C", 2e-12, "n1", "0"))
        # G_sum = 1/100 + 1/100 = 0.02, R_eff = 50
        # tau = 50 * 2e-12 = 1e-10
        tau = _compute_tau(g, "n1")
        assert tau == pytest.approx(1e-10)

    def test_no_cap_gives_inf(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        tau = _compute_tau(g, "n1")
        assert tau == float("inf")

    def test_no_resistor_gives_inf(self):
        g = RCGraph(port_nodes=["a"])
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        g._ensure_node("n1")
        tau = _compute_tau(g, "n1")
        assert tau == float("inf")


class TestTicerDegree1:
    def test_dangling_node(self):
        """Degree-1 internal node should be removed."""
        g = RCGraph(port_nodes=["a"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("C1", "C", 1e-12, "n1", "0"))
        reduce_ticer(g, tau_threshold=1e-6)
        assert "n1" not in g.nodes


class TestTicerDegree2:
    def test_series_reduction(self):
        """Degree-2 internal node: series R combination."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("R2", "R", 200.0, "n1", "b"))
        g.add_element(RCElement("C1", "C", 1e-15, "n1", "0"))
        reduce_ticer(g, tau_threshold=1e-6)
        # n1 should be eliminated, R1+R2 = 300
        assert "n1" not in g.nodes
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 1
        assert resistors[0].value == pytest.approx(300.0)


class TestTicerDegree3:
    def test_y_to_delta(self):
        """Y-network: center node eliminated via Y-to-Δ transform."""
        g = RCGraph(port_nodes=["p1", "p2", "p3"])
        g.add_element(RCElement("R1", "R", 100.0, "p1", "center"))
        g.add_element(RCElement("R2", "R", 100.0, "p2", "center"))
        g.add_element(RCElement("R3", "R", 100.0, "p3", "center"))
        g.add_element(RCElement("C1", "C", 1e-15, "center", "0"))
        reduce_ticer(g, tau_threshold=1.0)
        # center should be eliminated
        assert "center" not in g.nodes
        # Should have 3 delta resistors between p1-p2, p2-p3, p1-p3
        resistors = [e for e in g.elements.values() if e.etype == "R"]
        assert len(resistors) == 3
        # For equal Y resistors of R, delta = 3R = 300
        for r in resistors:
            assert r.value == pytest.approx(300.0)


class TestTicerThreshold:
    def test_high_tau_not_eliminated(self):
        """Node with tau above threshold should not be eliminated."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 1e6, "a", "n1"))
        g.add_element(RCElement("C1", "C", 1e-6, "n1", "0"))
        # tau = 1e6 * 1e-6 = 1.0
        reduce_ticer(g, tau_threshold=0.5)
        assert "n1" in g.nodes  # should NOT be eliminated

    def test_port_not_eliminated(self):
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "b"))
        g.add_element(RCElement("C1", "C", 1e-15, "a", "0"))
        reduce_ticer(g, tau_threshold=1.0)
        assert "a" in g.nodes
        assert "b" in g.nodes


class TestTicerCapRedistribution:
    def test_cap_redistributed(self):
        """Capacitance from eliminated node should be redistributed."""
        g = RCGraph(port_nodes=["a", "b"])
        g.add_element(RCElement("R1", "R", 100.0, "a", "n1"))
        g.add_element(RCElement("R2", "R", 100.0, "n1", "b"))
        g.add_element(RCElement("C1", "C", 2e-12, "n1", "0"))
        reduce_ticer(g, tau_threshold=1.0)
        # n1 eliminated; its 2pF should be split to a and b
        # Equal R means equal G: 50/50 split
        total_cap = sum(e.value for e in g.elements.values() if e.etype == "C")
        assert total_cap == pytest.approx(2e-12)
