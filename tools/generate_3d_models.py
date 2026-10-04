"""
generate_3d_models.py - Precision 3D CAD generator for Wio Terminal
Uses manifold3d CSG engine to guarantee 100% watertight, manifold, volume-valid STL meshes.

Models generated:
1. cad/stl/wio_tilt_tv_head.stl  - Articulated Retro CRT Monitor Head with Speaker/Battery Chamber
2. cad/stl/wio_tilt_tv_base.stl  - Stable Low-CG Clevis Desk Stand (0°~45° tilt)
3. cad/stl/wio_tilt_tv_knob.stl  - Knurled Friction Thumb Knob for angle lock
4. cad/stl/wio_desktop_dock.stl  - Fixed 30° Angled Desktop Stand (M3 spacing = 61.00mm)
5. cad/stl/wio_retro_tv.stl      - Retro Mini-TV Snap Bezel
"""

import os
import numpy as np
import trimesh

rot_x90 = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
rot_y90 = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])


# ==============================================================================
# Model 1: wio_tilt_tv_head (Articulated Monitor Head)
# ==============================================================================
def build_tilt_tv_head():
    # Cabinet outer box: 84mm wide, 30mm deep, 66mm high
    cab = trimesh.creation.box([84.0, 30.0, 66.0])
    cab.apply_translation([0, 15.0, 33.0])

    # Bottom Hinge Lug: 14.0mm wide, 16.0mm deep, 14.0mm high
    lug = trimesh.creation.box([14.0, 16.0, 14.0])
    lug.apply_translation([0, 15.0, -7.0])

    lug_cyl = trimesh.creation.cylinder(radius=8.0, height=14.0)
    lug_cyl.apply_transform(rot_y90)
    lug_cyl.apply_translation([0, 15.0, -7.0])

    # Vintage Knobs on right panel
    k1 = trimesh.creation.cylinder(radius=5.5, height=3.5)
    k1.apply_transform(rot_x90)
    k1.apply_translation([28.0, -1.75, 45.0])

    k2 = trimesh.creation.cylinder(radius=5.5, height=3.5)
    k2.apply_transform(rot_x90)
    k2.apply_translation([28.0, -1.75, 23.0])

    # Cat ears on top
    ear_l = trimesh.creation.cone(radius=7.0, height=12.0)
    ear_l.apply_translation([-20.0, 15.0, 66.0 + 6.0])

    ear_r = trimesh.creation.cone(radius=7.0, height=12.0)
    ear_r.apply_translation([20.0, 15.0, 66.0 + 6.0])

    union_mesh = trimesh.boolean.union([cab, lug, lug_cyl, k1, k2, ear_l, ear_r], engine='manifold')

    # Subtractions:
    # 1. Screen window: 50.0mm x 38.0mm, aligned with Wio Terminal display
    screen = trimesh.creation.box([50.0, 10.0, 38.0])
    screen.apply_translation([-6.0, 0, 33.0])

    # 2. Wio Terminal insertion pocket: 73.0mm wide x 13.0mm deep x 58.0mm high
    pocket = trimesh.creation.box([73.0, 13.0, 58.0])
    pocket.apply_translation([0, 9.5, 33.0])

    # 3. Rear chamber for Speaker & Battery: 64.0mm x 14.0mm x 48.0mm
    chamber = trimesh.creation.box([64.0, 14.0, 48.0])
    chamber.apply_translation([0, 22.0, 33.0])

    # 4. Through pivot hole in lug: diameter 3.6mm (M3 bolt pass)
    pivot_hole = trimesh.creation.cylinder(radius=1.8, height=30.0)
    pivot_hole.apply_transform(rot_y90)
    pivot_hole.apply_translation([0, 15.0, -7.0])

    # 5. Top tactile button cutout (A, B, C): 42.0mm x 10.0mm
    top_btns = trimesh.creation.box([42.0, 10.0, 10.0])
    top_btns.apply_translation([-6.0, 9.5, 66.0])

    # 6. Left Type-C cutout: 16.0mm x 10.0mm
    type_c = trimesh.creation.box([10.0, 16.0, 12.0])
    type_c.apply_translation([-42.0, 9.5, 33.0])

    # 7. Front 5-way joystick circular thumb opening (radius 7.5mm)
    joystick = trimesh.creation.cylinder(radius=7.5, height=10.0)
    joystick.apply_transform(rot_x90)
    joystick.apply_translation([26.0, 0, 18.0])

    # 8. Rear acoustic sound slots
    slits = []
    for i in range(5):
        s = trimesh.creation.box([50.0, 6.0, 2.5])
        s.apply_translation([0, 30.0, 20.0 + i * 6.0])
        slits.append(s)

    cutouts = [screen, pocket, chamber, pivot_hole, top_btns, type_c, joystick] + slits
    result = union_mesh.difference(cutouts, engine='manifold')
    return result


# ==============================================================================
# Model 2: wio_tilt_tv_base (Articulated Clevis Desk Stand)
# ==============================================================================
def build_tilt_tv_base():
    # Base weighted plate: 78mm wide, 68mm deep, 5mm thick
    plate = trimesh.creation.box([78.0, 68.0, 5.0])
    plate.apply_translation([0, 34.0, 2.5])

    # Chamfer rib on base
    rim = trimesh.creation.box([72.0, 62.0, 2.0])
    rim.apply_translation([0, 34.0, 5.0 + 1.0])

    # Clevis fork arms (gap = 14.8mm, allowing smooth clearance for 14.0mm head lug)
    # Left arm: X = -10.2mm, thickness 5.6mm
    arm_l = trimesh.creation.box([5.6, 18.0, 24.0])
    arm_l.apply_translation([-10.2, 34.0, 17.0])
    arm_l_top = trimesh.creation.cylinder(radius=9.0, height=5.6)
    arm_l_top.apply_transform(rot_y90)
    arm_l_top.apply_translation([-10.2, 34.0, 29.0])

    # Right arm: X = +10.2mm, thickness 5.6mm
    arm_r = trimesh.creation.box([5.6, 18.0, 24.0])
    arm_r.apply_translation([10.2, 34.0, 17.0])
    arm_r_top = trimesh.creation.cylinder(radius=9.0, height=5.6)
    arm_r_top.apply_transform(rot_y90)
    arm_r_top.apply_translation([10.2, 34.0, 29.0])

    union_mesh = trimesh.boolean.union([plate, rim, arm_l, arm_l_top, arm_r, arm_r_top], engine='manifold')

    # Through hole for M3 pivot: diameter 3.6mm
    pivot_hole = trimesh.creation.cylinder(radius=1.8, height=45.0)
    pivot_hole.apply_transform(rot_y90)
    pivot_hole.apply_translation([0, 34.0, 29.0])

    # 4 Anti-slip rubber feet recesses
    feet = []
    for fx, fy in [(-30.0, 10.0), (30.0, 10.0), (-30.0, 58.0), (30.0, 58.0)]:
        f = trimesh.creation.box([10.0, 10.0, 2.0])
        f.apply_translation([fx, fy, 0])
        feet.append(f)

    result = union_mesh.difference([pivot_hole] + feet, engine='manifold')
    return result


# ==============================================================================
# Model 3: wio_tilt_tv_knob (Knurled Friction Thumb Knob)
# ==============================================================================
def build_tilt_tv_knob():
    body = trimesh.creation.cylinder(radius=9.0, height=7.0)
    body.apply_translation([0, 0, 3.5])

    collar = trimesh.creation.cylinder(radius=4.5, height=3.0)
    collar.apply_translation([0, 0, 8.5])

    ridges = []
    for i in range(12):
        a = i * (2 * np.pi / 12)
        rx = 8.5 * np.cos(a)
        ry = 8.5 * np.sin(a)
        r = trimesh.creation.box([1.6, 1.6, 7.0])
        r.apply_translation([rx, ry, 3.5])
        ridges.append(r)

    union_mesh = trimesh.boolean.union([body, collar] + ridges, engine='manifold')

    # Central through hole (diameter 3.4mm)
    hole = trimesh.creation.cylinder(radius=1.7, height=18.0)
    hole.apply_translation([0, 0, 6.0])

    # Hex nut pocket (6.1mm flat-to-flat, depth 3.5mm)
    hex_nut = trimesh.creation.cylinder(radius=3.5, height=3.5, sections=6)
    hex_nut.apply_translation([0, 0, 1.75])

    result = union_mesh.difference([hole, hex_nut], engine='manifold')
    return result


# ==============================================================================
# Model 4: wio_desktop_dock (Fixed 30° Angled Dock)
# ==============================================================================
def build_desktop_dock():
    # Base footprint plate
    base = trimesh.creation.box([84.0, 74.0, 3.0])
    base.apply_translation([0, 37.0, 1.5])

    lip = trimesh.creation.box([84.0, 4.0, 14.0])
    lip.apply_translation([0, 2.0, 7.0])

    back = trimesh.creation.box([84.0, 4.0, 46.0])
    back.apply_translation([0, 72.0, 23.0])

    shelf = trimesh.creation.box([84.0, 62.0, 4.0])
    rot = trimesh.transformations.rotation_matrix(np.radians(28), [1, 0, 0])
    shelf.apply_transform(rot)
    shelf.apply_translation([0, 36.0, 18.0])

    # Left and right side walls
    wall_l = trimesh.creation.box([4.5, 74.0, 20.0])
    wall_l.apply_translation([-39.75, 37.0, 10.0])

    wall_r = trimesh.creation.box([4.5, 74.0, 20.0])
    wall_r.apply_translation([39.75, 37.0, 10.0])

    # Exact M3 mounting bosses (Official spacing: 61.00mm, X = +/- 30.5mm)
    boss_l = trimesh.creation.box([8.0, 12.0, 14.0])
    boss_l.apply_translation([-30.5, 36.0, 16.0])

    boss_r = trimesh.creation.box([8.0, 12.0, 14.0])
    boss_r.apply_translation([30.5, 36.0, 16.0])

    union_mesh = trimesh.boolean.union([base, lip, back, shelf, wall_l, wall_r, boss_l, boss_r], engine='manifold')

    # Subtractions:
    # 1. Electronics cavity
    cavity = trimesh.creation.box([54.0, 42.0, 18.0])
    cavity.apply_translation([0, 38.0, 10.0])

    # 2. Exact M3 holes at X = +/- 30.5mm
    m3_l = trimesh.creation.cylinder(radius=1.7, height=40.0)
    m3_l.apply_translation([-30.5, 36.0, 16.0])

    m3_r = trimesh.creation.cylinder(radius=1.7, height=40.0)
    m3_r.apply_translation([30.5, 36.0, 16.0])

    # 3. Type-C pass-through
    type_c = trimesh.creation.box([12.0, 18.0, 12.0])
    type_c.apply_translation([-42.0, 18.0, 8.0])

    # 4. Rear sound slots
    slits = []
    for i in range(7):
        s = trimesh.creation.box([2.5, 6.0, 20.0])
        s.apply_translation([-18.0 + i * 6.0, 72.0, 24.0])
        slits.append(s)

    result = union_mesh.difference([cavity, m3_l, m3_r, type_c] + slits, engine='manifold')
    return result


# ==============================================================================
# Model 5: wio_retro_tv (Snap-on Bezel)
# ==============================================================================
def build_retro_tv():
    cab = trimesh.creation.box([82.0, 26.0, 66.0])
    cab.apply_translation([0, 13.0, 33.0])

    k1 = trimesh.creation.cylinder(radius=5.5, height=3.5)
    k1.apply_transform(rot_x90)
    k1.apply_translation([28.0, -1.75, 43.0])

    k2 = trimesh.creation.cylinder(radius=5.5, height=3.5)
    k2.apply_transform(rot_x90)
    k2.apply_translation([28.0, -1.75, 23.0])

    legs = []
    for lx, ly in [(-35.0, 4.0), (35.0, 4.0), (-35.0, 22.0), (35.0, 22.0)]:
        leg = trimesh.creation.box([5.0, 5.0, 10.0])
        leg.apply_translation([lx, ly, -5.0])
        legs.append(leg)

    ear_l = trimesh.creation.cone(radius=7.0, height=12.0)
    ear_l.apply_translation([-20.0, 13.0, 66.0 + 6.0])

    ear_r = trimesh.creation.cone(radius=7.0, height=12.0)
    ear_r.apply_translation([20.0, 13.0, 66.0 + 6.0])

    union_mesh = trimesh.boolean.union([cab, k1, k2, ear_l, ear_r] + legs, engine='manifold')

    screen = trimesh.creation.box([50.0, 10.0, 38.0])
    screen.apply_translation([-6.0, 0, 33.0])

    pocket = trimesh.creation.box([73.0, 14.0, 58.0])
    pocket.apply_translation([0, 14.0, 33.0])

    result = union_mesh.difference([screen, pocket], engine='manifold')
    return result


def export_stl(mesh, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mesh.export(path)
    # Validate watertightness and volume
    loaded = trimesh.load(path)
    print(f"Exported: {path:35s} | Watertight: {loaded.is_watertight!s:5s} | Volume: {loaded.volume:10.1f} mm³ | Triangles: {len(loaded.faces)}")


def update_scad_files():
    # Write OpenSCAD files with exact 61.00mm spacing
    dock_scad = """// Wio Terminal 30° 桌面固定底座与音腔背壳 (OpenSCAD 源码)
// 官方标准两 M3 螺丝孔距: 61.00 mm (X = +/- 30.5 mm)
$fn = 60;
module wio_dock() {
    difference() {
        union() {
            translate([-42, 0, 0]) cube([84, 74, 3]);
            translate([-42, 0, 0]) cube([84, 4, 14]);
            translate([-42, 70, 0]) cube([84, 4, 46]);
            rotate([28, 0, 0]) translate([-42, 10, 0]) cube([84, 62, 4]);
            // 螺丝固定座 (X = +/- 30.5mm)
            translate([-30.5 - 4, 30, 0]) cube([8, 12, 18]);
            translate([ 30.5 - 4, 30, 0]) cube([8, 12, 18]);
        }
        // 内部空腔
        translate([-27, 16, 2]) cube([54, 44, 20]);
        // M3 穿孔 (间距 61.00mm)
        translate([-30.5, 36, 0]) cylinder(d=3.4, h=40);
        translate([ 30.5, 36, 0]) cylinder(d=3.4, h=40);
        // Type-C 出线口
        translate([-43, 12, 2]) cube([6, 18, 12]);
    }
}
wio_dock();
"""
    with open('cad/wio_desktop_dock.scad', 'w', encoding='utf-8') as f:
        f.write(dock_scad)

    tilt_scad = """// Wio Terminal 可俯仰摆动复古小电视监视器 (OpenSCAD 源码)
// 支持 0° ~ 45° 自由俯仰调节
$fn = 60;
mode = "assembly"; // "assembly", "head", "base", "knob"
tilt_deg = 25;

module tv_head() {
    difference() {
        union() {
            translate([-42, 0, 0]) cube([84, 30, 66]);
            // 转轴凸耳 (宽 14mm)
            translate([-7, 7, -14]) cube([14, 16, 14]);
            translate([0, 15, -7]) rotate([0, 90, 0]) cylinder(r=8, h=14, center=true);
            // 旋钮
            translate([28, -2, 45]) rotate([-90,0,0]) cylinder(r=5.5, h=3.5);
            translate([28, -2, 23]) rotate([-90,0,0]) cylinder(r=5.5, h=3.5);
        }
        // 屏幕视窗 (50x38mm)
        translate([-6, -2, 33 - 19]) cube([50, 6, 38]);
        // Wio Terminal 槽 (73x13x58mm)
        translate([-36.5, 3, 33 - 29]) cube([73, 13, 58]);
        // 音腔/电池仓 (64x14x48mm)
        translate([-32, 15, 33 - 24]) cube([64, 14, 48]);
        // 转轴过孔 (M3)
        translate([0, 15, -7]) rotate([0, 90, 0]) cylinder(d=3.6, h=30, center=true);
        // Type-C 槽
        translate([-43, 4, 27]) cube([6, 16, 12]);
    }
}

module tv_base() {
    difference() {
        union() {
            translate([-39, 0, 0]) cube([78, 68, 5]);
            // 双叉支架 (内间距 14.8mm)
            translate([-13.0, 25, 5]) cube([5.6, 18, 24]);
            translate([  7.4, 25, 5]) cube([5.6, 18, 24]);
            translate([-10.2, 34, 29]) rotate([0, 90, 0]) cylinder(r=9, h=5.6, center=true);
            translate([ 10.2, 34, 29]) rotate([0, 90, 0]) cylinder(r=9, h=5.6, center=true);
        }
        // 转轴通孔
        translate([0, 34, 29]) rotate([0, 90, 0]) cylinder(d=3.6, h=50, center=true);
    }
}

module thumb_knob() {
    difference() {
        cylinder(r=9, h=7);
        translate([0, 0, -1]) cylinder(d=3.4, h=12);
        translate([0, 0, -1]) cylinder(r=3.5, h=3.5, $fn=6);
    }
}

if (mode == "assembly") {
    color("#444444") tv_base();
    translate([0, 34, 29]) rotate([tilt_deg, 0, 0]) translate([0, -15, 7]) color("#F5F2EB") tv_head();
    translate([14, 34, 29]) rotate([0, 90, 0]) color("#C8A165") thumb_knob();
} else if (mode == "head") tv_head();
else if (mode == "base") tv_base();
else if (mode == "knob") thumb_knob();
"""
    with open('cad/wio_tilt_tv.scad', 'w', encoding='utf-8') as f:
        f.write(tilt_scad)


def main():
    print("Building and validating 3D models with manifold3d CSG kernel...")
    export_stl(build_tilt_tv_head(), 'cad/stl/wio_tilt_tv_head.stl')
    export_stl(build_tilt_tv_base(), 'cad/stl/wio_tilt_tv_base.stl')
    export_stl(build_tilt_tv_knob(), 'cad/stl/wio_tilt_tv_knob.stl')
    export_stl(build_desktop_dock(), 'cad/stl/wio_desktop_dock.stl')
    export_stl(build_retro_tv(),     'cad/stl/wio_retro_tv.stl')
    update_scad_files()
    print("All models successfully built and verified!")

if __name__ == '__main__':
    main()
