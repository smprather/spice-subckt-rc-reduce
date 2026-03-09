"""Integration tests — full pipeline from file to file."""

import pytest
from pathlib import Path
from rcreduce.parser import parse_file, write_file
from rcreduce.graph import from_subcircuit, to_subcircuit
from rcreduce.ticer import reduce_ticer
from rcreduce.merge import reduce_merge

TESTDATA = Path(__file__).parent.parent / "testdata"


class TestMergeIntegration:
    def test_simple_rc_chain(self, tmp_path):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        original_ports = set(subckt.ports)
        reduce_merge(g)

        result = to_subcircuit(g, subckt)
        assert set(result.ports) == original_ports

        # Write and re-parse to confirm valid SPICE
        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)
        sf2 = parse_file(out)
        assert len(sf2.subcircuits) == 1
        assert sf2.subcircuits[0].ports == subckt.ports

    def test_rc_pi(self, tmp_path):
        sf = parse_file(TESTDATA / "rc_pi.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        n_before = len(g.elements)
        reduce_merge(g)
        n_after = len(g.elements)
        assert n_after < n_before  # should reduce

        result = to_subcircuit(g, subckt)
        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)
        sf2 = parse_file(out)
        assert sf2.subcircuits[0].ports == ["in", "out"]

    def test_passthrough_preserved(self, tmp_path):
        sf = parse_file(TESTDATA / "passthrough.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        # Count passthrough elements before
        n_passthrough = len(g.passthrough_elements)

        reduce_merge(g)

        result = to_subcircuit(g, subckt)
        # Passthrough elements should be unchanged
        passthrough_lines = [
            e.raw_line for e in result.elements if e.value is None
        ]
        assert len(passthrough_lines) == n_passthrough
        # M1 should still be there
        assert any("M1" in line for line in passthrough_lines)

        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)
        content = out.read_text()
        assert "M1" in content
        assert "PMOS" in content


class TestTicerIntegration:
    def test_simple_rc_chain(self, tmp_path):
        sf = parse_file(TESTDATA / "simple_rc_chain.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        original_ports = set(subckt.ports)
        n_before = len(g.elements)
        reduce_ticer(g, tau_threshold=1e-6)
        n_after = len(g.elements)
        assert n_after <= n_before

        result = to_subcircuit(g, subckt)
        assert set(result.ports) == original_ports

        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)
        sf2 = parse_file(out)
        assert sf2.subcircuits[0].ports == subckt.ports

    def test_rc_star(self, tmp_path):
        sf = parse_file(TESTDATA / "rc_star.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        reduce_ticer(g, tau_threshold=1.0)

        # center node should be eliminated
        assert "center" not in g.nodes
        # Port nodes preserved
        assert "p1" in g.nodes
        assert "p2" in g.nodes
        assert "p3" in g.nodes

        result = to_subcircuit(g, subckt)
        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)
        sf2 = parse_file(out)
        assert sf2.subcircuits[0].ports == ["p1", "p2", "p3"]

    def test_large_mesh_reduces(self, tmp_path):
        sf = parse_file(TESTDATA / "large_mesh.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        n_before = len(g.elements)
        reduce_ticer(g, tau_threshold=1e-6)
        n_after = len(g.elements)

        # Should reduce significantly
        assert n_after < n_before

        result = to_subcircuit(g, subckt)
        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)

        # Output should be valid SPICE
        sf2 = parse_file(out)
        assert len(sf2.subcircuits) == 1
        # Port nodes must be preserved
        assert sf2.subcircuits[0].ports == subckt.ports

    def test_passthrough_with_ticer(self, tmp_path):
        sf = parse_file(TESTDATA / "passthrough.subckt")
        subckt = sf.subcircuits[0]
        g = from_subcircuit(subckt)

        reduce_ticer(g, tau_threshold=1e-6)

        result = to_subcircuit(g, subckt)
        out = tmp_path / "reduced.subckt"
        sf.subcircuits[0] = result
        write_file(sf, out)

        content = out.read_text()
        assert "M1" in content
        assert "Xbuf" in content


class TestPortPreservation:
    """Verify that port nodes are always preserved."""

    @pytest.mark.parametrize("testfile", [
        "simple_rc_chain.subckt",
        "rc_pi.subckt",
        "rc_star.subckt",
        "passthrough.subckt",
        "large_mesh.subckt",
    ])
    def test_ports_preserved_ticer(self, testfile):
        sf = parse_file(TESTDATA / testfile)
        subckt = sf.subcircuits[0]
        original_ports = set(subckt.ports)
        g = from_subcircuit(subckt)
        reduce_ticer(g, tau_threshold=1e-6)
        assert original_ports.issubset(g.nodes)

    @pytest.mark.parametrize("testfile", [
        "simple_rc_chain.subckt",
        "rc_pi.subckt",
        "rc_star.subckt",
        "passthrough.subckt",
    ])
    def test_ports_preserved_merge(self, testfile):
        sf = parse_file(TESTDATA / testfile)
        subckt = sf.subcircuits[0]
        original_ports = set(subckt.ports)
        g = from_subcircuit(subckt)
        reduce_merge(g)
        assert original_ports.issubset(g.nodes)
