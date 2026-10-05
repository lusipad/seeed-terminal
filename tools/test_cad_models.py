"""
test_cad_models.py - Automated verification harness for the 3D printable STL files
"""

import os
import trimesh

PARTS = ['head', 'rear_cover', 'base', 'bottom_cover', 'front_panel', 'knob']
JLC_PARTS = ['01_jlc_monitor', '02_jlc_base']


def run_tests():
    files = [f'cad/stl/wio_tilt_tv_{p}.stl' for p in PARTS]

    all_passed = True
    total = 0.0
    print("=" * 75)
    print("3D CAD / STL Automated Quality Inspection (watertight, single shell, <= 100mm)")
    print("=" * 75)

    for f in files:
        assert os.path.exists(f), f"File missing: {f}"
        mesh = trimesh.load(f)

        wt = mesh.is_watertight
        vol_cm3 = mesh.volume / 1000.0
        bounds = mesh.extents
        weight = vol_cm3 * 1.15
        num_shells = len(mesh.split(only_watertight=False))
        total += vol_cm3

        status = "PASS" if wt and vol_cm3 > 0 and num_shells == 1 and max(bounds) <= 100.0 else "FAIL"
        if status == "FAIL":
            all_passed = False

        print(f"[{status}] {os.path.basename(f):32s} | Shells: {num_shells} | {vol_cm3:5.2f}cm³ | {weight:4.1f}g | {bounds[0]:.1f}x{bounds[1]:.1f}x{bounds[2]:.1f}mm")

    print("-" * 75)
    print(f"Total printed volume: {total:.2f} cm³ (~{total * 1.15:.0f} g in 9600 resin)")
    assert all_passed, "Some test cases failed!"

    # JLC free 3D printing set: max 2 parts per order, total <= 70 cm3, every part <= 100mm, 1 shell
    print("-" * 75)
    jlc = [f'cad/stl/jlc_free/{n}.stl' for n in JLC_PARTS]
    v_total = 0.0
    for f in jlc:
        assert os.path.exists(f), f"File missing: {f}"
        m = trimesh.load(f)
        v = m.volume / 1000.0
        v_total += v
        assert m.is_watertight, f"{f} is not watertight!"
        assert len(m.split(only_watertight=False)) == 1, f"{f} is not a single shell!"
        for dim, axis in zip(m.extents, 'XYZ'):
            assert dim <= 100.0, f"{f} {axis} exceeds 100mm: {dim}"
        print(f"[PASS] {os.path.basename(f):32s} | {v:5.2f}cm³ | {m.extents[0]:.1f}x{m.extents[1]:.1f}x{m.extents[2]:.1f}mm")
    assert len(jlc) <= 2
    assert v_total <= 70.0, f"JLC set exceeds 70 cm3: {v_total:.2f}"
    print(f"JLC free set: {len(jlc)} parts, {v_total:.2f} cm³ (limit 70.00 cm³)")
    print("=" * 75)
    print("ALL PARTS WATERTIGHT, SINGLE SHELL AND <= 100mm; JLC FREE SET WITHIN LIMITS")
    print("=" * 75)


if __name__ == '__main__':
    run_tests()
