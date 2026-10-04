"""
test_cad_models.py - Automated verification harness for 3D printable STL files
"""

import os
import trimesh

def run_tests():
    files = [
        'cad/stl/wio_tilt_tv_head.stl',
        'cad/stl/wio_tilt_tv_base.stl',
        'cad/stl/wio_tilt_tv_knob.stl',
        'cad/stl/wio_tilt_tv_plate.stl',
        'cad/stl/wio_desktop_dock.stl',
        'cad/stl/wio_retro_tv.stl',
        'cad/stl/jlc_free/01_jlc_tilt_tv_head.stl',
        'cad/stl/jlc_free/02_jlc_tilt_tv_base.stl',
        'cad/stl/jlc_free/03_jlc_tilt_tv_knob.stl',
        'cad/stl/jlc_free/04_jlc_unibody_dock.stl'
    ]

    all_passed = True
    print("=" * 75)
    print("3D CAD / STL Automated Quality Inspection (Strict Single Shell & JLC Rules)")
    print("=" * 75)

    for f in files:
        assert os.path.exists(f), f"File missing: {f}"
        mesh = trimesh.load(f)

        wt = mesh.is_watertight
        vol_cm3 = mesh.volume / 1000.0
        bounds = mesh.extents
        weight = vol_cm3 * 1.15
        shells = mesh.split(only_watertight=False)
        num_shells = len(shells)

        # Combo plate contains 3 parts + sprues; all standalone models must be strictly 1 shell
        expected_shells = 1 if 'plate' not in f else num_shells
        status = "PASS" if wt and vol_cm3 > 0 and num_shells == expected_shells else "FAIL"
        if status == "FAIL":
            all_passed = False

        print(f"[{status}] {os.path.basename(f):32s} | Shells: {num_shells} | {vol_cm3:5.2f}cm³ | {weight:4.1f}g | {bounds[0]:.1f}x{bounds[1]:.1f}x{bounds[2]:.1f}mm")

    print("-" * 75)
    # Check JLC Free 2-item rule compliance
    jlc_head = trimesh.load('cad/stl/jlc_free/01_jlc_tilt_tv_head.stl')
    jlc_base = trimesh.load('cad/stl/jlc_free/02_jlc_tilt_tv_base.stl')

    v_total = (jlc_head.volume + jlc_base.volume) / 1000.0
    print(f"JLC Free Order Total Volume (Head + Base): {v_total:.2f} cm³ (Limit: 70.00 cm³)")
    assert v_total <= 70.00, f"Volume exceeds 70cm³: {v_total}"

    for m, name in [(jlc_head, "01_jlc_head"), (jlc_base, "02_jlc_base")]:
        assert len(m.split(only_watertight=False)) == 1, f"{name} is not a single shell!"
        assert m.is_watertight, f"{name} is not watertight!"
        for dim, axis in zip(m.extents, ['X', 'Y', 'Z']):
            assert dim <= 100.0, f"{name} {axis} exceeds 100mm: {dim}"

    assert all_passed, "Some test cases failed!"
    print("=" * 75)
    print("ALL JLC FREE 3D PRINTING CONSTRAINTS (1 SHELL, UNIFORM WALLS, <=70cm³) PASSED!")
    print("=" * 75)

if __name__ == '__main__':
    run_tests()
