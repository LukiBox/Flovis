"""Control surfaces: defaults per layout, project round trip, validation."""
from __future__ import annotations

from flovis.core.geometry import (AircraftModel, ControlKind, ControlSurface,
                                  Layout, default_control_surfaces,
                                  make_template)
from flovis.core.project import load_project, save_project


def test_templates_carry_control_surfaces():
    for layout in Layout:
        m = make_template(layout)
        assert m.control_surfaces, f"{layout.value} has no control surfaces"
        kinds = {c.kind for c in m.control_surfaces}
        if layout == Layout.FLYING_WING:
            assert kinds == {ControlKind.ELEVON}
        else:
            assert ControlKind.AILERON in kinds
            assert ControlKind.ELEVATOR in kinds
        # every parent must actually exist
        names = {s.name for s in m.surfaces}
        assert all(c.parent in names for c in m.control_surfaces)


def test_extents_are_validated():
    cs = ControlSurface(ControlKind.AILERON, "Wing", -0.2, 1.4,
                        chord_fraction=0.01)
    assert 0.0 <= cs.span_start < cs.span_end <= 1.0
    assert cs.chord_fraction >= 0.05


def test_project_round_trip(tmp_path):
    m = make_template(Layout.HIGH_WING)
    m.control_surfaces[0].span_start = 0.55
    m.control_surfaces[0].max_deflection_deg = 18.0
    p = save_project(tmp_path / "t.flovis", model=m)
    back = load_project(p)["model"]
    assert [c.to_dict() for c in back.control_surfaces] \
        == [c.to_dict() for c in m.control_surfaces]


def test_old_project_without_controls_gets_defaults():
    d = make_template(Layout.LOW_WING).to_dict()
    del d["control_surfaces"]                     # pre-upgrade project
    back = AircraftModel.from_dict(d)
    assert back.control_surfaces                  # seeded on load
    assert back.control_surfaces == default_control_surfaces(
        back.layout, back.surfaces)
