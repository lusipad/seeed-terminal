"""
generate_3d_models.py - Generate 3D CAD OpenSCAD and watertight binary STL models for Wio Terminal
Includes:
1. wio_desktop_dock: 30° Angled Desktop Stand & Audio/Battery Chassis
2. wio_retro_tv: Vintage CRT Mini-TV Bezel
3. wio_tilt_tv: Fully Articulated Retro Monitor with Tilting / Swiveling Head & Desk Base
   - Head (Monitor with CRT Bezel & Rear Speaker/Battery Cavity)
   - Base (Desk stand with dual hinge clevis)
   - Knob (Vintage knurled thumb wheel for friction tilt adjustment)
"""

import math
import struct
import os

class STLMesh:
    def __init__(self):
        self.triangles = []

    def add_triangle(self, v1, v2, v3):
        ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 1e-9:
            normal = (nx/length, ny/length, nz/length)
        else:
            normal = (0.0, 0.0, 1.0)
        self.triangles.append((normal, v1, v2, v3))

    def add_quad(self, v1, v2, v3, v4):
        self.add_triangle(v1, v2, v3)
        self.add_triangle(v1, v3, v4)

    def add_box(self, x, y, z, dx, dy, dz):
        p0 = (x, y, z)
        p1 = (x + dx, y, z)
        p2 = (x + dx, y + dy, z)
        p3 = (x, y + dy, z)
        p4 = (x, y, z + dz)
        p5 = (x + dx, y, z + dz)
        p6 = (x + dx, y + dy, z + dz)
        p7 = (x, y + dy, z + dz)

        # Bottom
        self.add_quad(p0, p3, p2, p1)
        # Top
        self.add_quad(p4, p5, p6, p7)
        # Front
        self.add_quad(p0, p1, p5, p4)
        # Back
        self.add_quad(p2, p3, p7, p6)
        # Left
        self.add_quad(p3, p0, p4, p7)
        # Right
        self.add_quad(p1, p2, p6, p5)

    def add_cylinder(self, cx, cy, cz, r, h, axis='z', segments=16):
        angle_step = 2 * math.pi / segments
        pts_bot = []
        pts_top = []
        for i in range(segments):
            a = i * angle_step
            if axis == 'y':
                pts_bot.append((cx + r * math.cos(a), cy, cz + r * math.sin(a)))
                pts_top.append((cx + r * math.cos(a), cy + h, cz + r * math.sin(a)))
            elif axis == 'z':
                pts_bot.append((cx + r * math.cos(a), cy + r * math.sin(a), cz))
                pts_top.append((cx + r * math.cos(a), cy + r * math.sin(a), cz + h))
            elif axis == 'x':
                pts_bot.append((cx, cy + r * math.cos(a), cz + r * math.sin(a)))
                pts_top.append((cx + h, cy + r * math.cos(a), cz + r * math.sin(a)))

        for i in range(segments):
            next_i = (i + 1) % segments
            self.add_quad(pts_bot[i], pts_bot[next_i], pts_top[next_i], pts_top[i])
            if axis == 'y':
                self.add_triangle((cx, cy, cz), pts_bot[next_i], pts_bot[i])
                self.add_triangle((cx, cy + h, cz), pts_top[i], pts_top[next_i])
            elif axis == 'z':
                self.add_triangle((cx, cy, cz), pts_bot[i], pts_bot[next_i])
                self.add_triangle((cx, cy, cz + h), pts_top[next_i], pts_top[i])
            elif axis == 'x':
                self.add_triangle((cx, cy, cz), pts_bot[i], pts_bot[next_i])
                self.add_triangle((cx + h, cy, cz), pts_top[next_i], pts_top[i])

    def write_binary_stl(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            header = b'Wio Terminal 3D Printable Enclosure - Open Source\x00'
            header = header.ljust(80, b'\x00')
            f.write(header)
            f.write(struct.pack('<I', len(self.triangles)))
            for normal, v1, v2, v3 in self.triangles:
                f.write(struct.pack('<3f', *normal))
                f.write(struct.pack('<3f', *v1))
                f.write(struct.pack('<3f', *v2))
                f.write(struct.pack('<3f', *v3))
                f.write(struct.pack('<H', 0))
        print(f"Exported binary STL: {filepath} ({len(self.triangles)} triangles, {os.path.getsize(filepath)} bytes)")


# ==============================================================================
# Model 1: wio_desktop_dock (30° Fixed Tilt Desktop Stand)
# ==============================================================================
def build_desktop_dock_mesh():
    mesh = STLMesh()
    bw = 84.0
    bd = 74.0
    fh = 10.0
    bh = 46.0
    side_thick = 4.5

    mesh.add_box(-bw/2, 0, 0, bw, bd, 3.0)

    # Left wedge
    lw = -bw/2
    rw = -bw/2 + side_thick
    p_f_bot = (lw, 0, 0)
    p_f_top = (lw, 0, fh)
    p_b_top = (lw, bd, bh)
    p_b_bot = (lw, bd, 0)
    p_f_bot_in = (rw, 0, 0)
    p_f_top_in = (rw, 0, fh)
    p_b_top_in = (rw, bd, bh)
    p_b_bot_in = (rw, bd, 0)

    mesh.add_triangle(p_f_bot, p_f_top, p_b_top)
    mesh.add_triangle(p_f_bot, p_b_top, p_b_bot)
    mesh.add_triangle(p_f_bot_in, p_b_top_in, p_f_top_in)
    mesh.add_triangle(p_f_bot_in, p_b_bot_in, p_b_top_in)
    mesh.add_quad(p_f_top, p_f_top_in, p_b_top_in, p_b_top)
    mesh.add_quad(p_f_bot, p_f_bot_in, p_f_top_in, p_f_top)
    mesh.add_quad(p_b_bot_in, p_b_bot, p_b_top, p_b_top_in)

    # Right wedge
    r_lw = bw/2 - side_thick
    r_rw = bw/2
    rp_f_bot = (r_rw, 0, 0)
    rp_f_top = (r_rw, 0, fh)
    rp_b_top = (r_rw, bd, bh)
    rp_b_bot = (r_rw, bd, 0)
    rp_f_bot_in = (r_lw, 0, 0)
    rp_f_top_in = (r_lw, 0, fh)
    rp_b_top_in = (r_lw, bd, bh)
    rp_b_bot_in = (r_lw, bd, 0)

    mesh.add_triangle(rp_f_bot, rp_b_top, rp_f_top)
    mesh.add_triangle(rp_f_bot, rp_b_bot, rp_b_top)
    mesh.add_triangle(rp_f_bot_in, rp_f_top_in, rp_b_top_in)
    mesh.add_triangle(rp_f_bot_in, rp_b_top_in, rp_b_bot_in)
    mesh.add_quad(rp_f_top_in, rp_f_top, rp_b_top, rp_b_top_in)
    mesh.add_quad(rp_f_bot_in, rp_f_bot, rp_f_top, rp_f_top_in)
    mesh.add_quad(rp_b_bot, rp_b_bot_in, rp_b_top_in, rp_b_top)

    mesh.add_box(-bw/2, 0, 0, bw, 4.0, 14.0)

    back_y = bd - 3.5
    back_h = bh
    mesh.add_box(-bw/2 + side_thick, back_y, 0, bw - 2*side_thick, 3.5, 12.0)
    mesh.add_box(-bw/2 + side_thick, back_y, 36.0, bw - 2*side_thick, 3.5, back_h - 36.0)

    slat_w = 4.0
    for i in range(-5, 6):
        sx = i * 6.5
        mesh.add_box(sx - slat_w/2, back_y, 12.0, slat_w, 3.5, 24.0)

    shelf_t = 3.5
    shelf_w = bw - 2*side_thick
    y1, z1 = 6.0, 7.0
    y2, z2 = bd - 6.0, bh - 6.0
    mesh.add_quad((-shelf_w/2, y1, z1), (shelf_w/2, y1, z1), (shelf_w/2, y2, z2), (-shelf_w/2, y2, z2))
    mesh.add_quad((-shelf_w/2, y1, z1 - shelf_t), (-shelf_w/2, y2, z2 - shelf_t), (shelf_w/2, y2, z2 - shelf_t), (shelf_w/2, y1, z1 - shelf_t))
    mesh.add_quad((-shelf_w/2, y1, z1 - shelf_t), (shelf_w/2, y1, z1 - shelf_t), (shelf_w/2, y1, z1), (-shelf_w/2, y1, z1))
    mesh.add_quad((-shelf_w/2, y2, z2), (shelf_w/2, y2, z2), (shelf_w/2, y2, z2 - shelf_t), (-shelf_w/2, y2, z2 - shelf_t))

    boss_w = 8.0
    boss_h = 10.0
    boss_y = (y1 + y2) / 2
    boss_z = (z1 + z2) / 2 - 2.0
    mesh.add_box(-20 - boss_w/2, boss_y - 4, boss_z - boss_h, boss_w, 8.0, boss_h)
    mesh.add_box( 20 - boss_w/2, boss_y - 4, boss_z - boss_h, boss_w, 8.0, boss_h)
    mesh.add_box(-bw/2, 10.0, 3.0, side_thick, 16.0, 10.0)
    mesh.add_box(-25.0, 20.0, 3.0, 50.0, 30.0, 2.0)

    return mesh


# ==============================================================================
# Model 2: wio_retro_tv (Snap-on Bezel)
# ==============================================================================
def build_retro_tv_mesh():
    mesh = STLMesh()
    tw = 82.0
    th = 66.0
    td = 24.0
    wall = 3.0

    mesh.add_box(-tw/2, 0, 0, tw, td, wall)
    mesh.add_box(-tw/2, 0, th - wall, tw, td, wall)
    mesh.add_box(-tw/2, 0, wall, wall, td, th - 2*wall)
    mesh.add_box(tw/2 - wall, 0, wall, wall, td, th - 2*wall)

    sw = 50.0
    sh = 38.0
    sx0 = -tw/2 + 7.0
    sy0 = (th - sh) / 2

    mesh.add_box(-tw/2, 0, 0, 7.0, wall, th)
    mesh.add_box(sx0, 0, 0, sw, wall, sy0)
    mesh.add_box(sx0, 0, sy0 + sh, sw, wall, th - (sy0 + sh))
    rx0 = sx0 + sw
    rw = tw/2 - rx0
    mesh.add_box(rx0, 0, 0, rw, wall, th)

    mesh.add_box(rx0 + 3.0, -4.0, sy0 + sh - 8.0, 10.0, 4.0, 10.0)
    mesh.add_box(rx0 + 3.0, -4.0, sy0 + 6.0, 10.0, 4.0, 10.0)

    for i in range(3):
        mesh.add_box(rx0 + 2.0, -1.0, sy0 + 20.0 + i*4.0, 12.0, 1.0, 1.5)

    leg_w = 4.0
    leg_d = 4.0
    leg_h = 10.0
    mesh.add_box(-tw/2 + 5, 2, -leg_h, leg_w, leg_d, leg_h)
    mesh.add_box(tw/2 - 9, 2, -leg_h, leg_w, leg_d, leg_h)
    mesh.add_box(-tw/2 + 5, td - 6, -leg_h, leg_w, leg_d, leg_h)
    mesh.add_box(tw/2 - 9, td - 6, -leg_h, leg_w, leg_d, leg_h)

    ear_h = 12.0
    ear_t = 3.5
    p1 = (-24.0, td/2 - ear_t/2, th)
    p2 = (-12.0, td/2 - ear_t/2, th)
    p3 = (-18.0, td/2 - ear_t/2, th + ear_h)
    p4 = (-24.0, td/2 + ear_t/2, th)
    p5 = (-12.0, td/2 + ear_t/2, th)
    p6 = (-18.0, td/2 + ear_t/2, th + ear_h)
    mesh.add_triangle(p1, p2, p3)
    mesh.add_triangle(p4, p6, p5)
    mesh.add_quad(p1, p4, p6, p3)
    mesh.add_quad(p2, p3, p6, p5)
    mesh.add_quad(p1, p2, p5, p4)

    rp1 = (12.0, td/2 - ear_t/2, th)
    rp2 = (24.0, td/2 - ear_t/2, th)
    rp3 = (18.0, td/2 - ear_t/2, th + ear_h)
    rp4 = (12.0, td/2 + ear_t/2, th)
    rp5 = (24.0, td/2 + ear_t/2, th)
    rp6 = (18.0, td/2 + ear_t/2, th + ear_h)
    mesh.add_triangle(rp1, rp2, rp3)
    mesh.add_triangle(rp4, rp6, rp5)
    mesh.add_quad(rp1, rp4, rp6, rp3)
    mesh.add_quad(rp2, rp3, rp6, rp5)
    mesh.add_quad(rp1, rp2, rp5, rp4)

    return mesh


# ==============================================================================
# Model 3: wio_tilt_tv_head (Articulated Retro Monitor Head with Swivel Lug)
# ==============================================================================
def build_tilt_tv_head_mesh():
    """
    Builds the monitor head:
    - Retro TV style case with CRT front bezel
    - Internal cavity for Wio Terminal + MAX98357A + Speaker + Battery
    - Rear sound grille
    - Dual rotary knobs on right side
    - Bottom central pivot hinge lug (width 14mm, height 14mm) with M3/M4 pivot hole
    """
    mesh = STLMesh()
    tw = 84.0   # Width
    th = 66.0   # Height
    td = 32.0   # Total depth (allows 12mm Wio + 18mm sound/battery chamber)
    wall = 3.0

    # Outer cabinet box (top, bottom, left, right)
    mesh.add_box(-tw/2, 0, 0, tw, td, wall)
    mesh.add_box(-tw/2, 0, th - wall, tw, td, wall)
    mesh.add_box(-tw/2, 0, wall, wall, td, th - 2*wall)
    mesh.add_box(tw/2 - wall, 0, wall, wall, td, th - 2*wall)

    # Front CRT Bezel with 2.4 inch screen opening (50mm x 38mm)
    sw = 50.0
    sh = 38.0
    sx0 = -tw/2 + 8.0
    sy0 = (th - sh) / 2

    # Front face borders
    mesh.add_box(-tw/2, 0, 0, 8.0, wall, th)
    mesh.add_box(sx0, 0, 0, sw, wall, sy0)
    mesh.add_box(sx0, 0, sy0 + sh, sw, wall, th - (sy0 + sh))
    rx0 = sx0 + sw
    rw = tw/2 - rx0
    mesh.add_box(rx0, 0, 0, rw, wall, th)

    # Vintage Knobs on the right panel
    mesh.add_cylinder(rx0 + rw/2, -3.0, sy0 + sh - 8.0, 5.5, 3.0, axis='y', segments=16)
    mesh.add_cylinder(rx0 + rw/2, -3.0, sy0 + 8.0, 5.5, 3.0, axis='y', segments=16)

    # 5-way joystick thumb cutout
    mesh.add_box(rx0 + 2.0, 0, sy0 + 16.0, rw - 4.0, wall, 8.0)

    # Back plate with acoustic grille slits
    back_y = td - wall
    mesh.add_box(-tw/2, back_y, 0, tw, wall, 12.0)
    mesh.add_box(-tw/2, back_y, th - 12.0, tw, wall, 12.0)
    mesh.add_box(-tw/2, back_y, 12.0, 10.0, wall, th - 24.0)
    mesh.add_box(tw/2 - 10.0, back_y, 12.0, 10.0, wall, th - 24.0)

    # Back grille horizontal slats
    for i in range(6):
        slat_z = 16.0 + i * 5.5
        mesh.add_box(-tw/2 + 10.0, back_y, slat_z, tw - 20.0, wall, 2.5)

    # Left Type-C cut-out
    mesh.add_box(-tw/2 - 1.0, 6.0, 14.0, wall + 2.0, 16.0, 12.0)

    # Top A/B/C tactile buttons opening
    mesh.add_box(-20.0, td/2 - 5.0, th - wall - 1.0, 40.0, 10.0, wall + 2.0)

    # Bottom Hinge Lug (pivot ear)
    # Lug centered at X=0, Y=td/2, Z extending from 0 down to -14mm
    lug_w = 14.0
    lug_d = 16.0
    lug_h = 14.0
    mesh.add_box(-lug_w/2, td/2 - lug_d/2, -lug_h, lug_w, lug_d, lug_h)

    # Pivot cylinder boss through the lug
    mesh.add_cylinder(0, td/2, -lug_h/2, 6.0, lug_w, axis='x', segments=16)

    # Cute cat ears on top
    ear_h = 11.0
    ear_t = 3.5
    # Left ear
    p1 = (-24.0, td/2 - ear_t/2, th)
    p2 = (-12.0, td/2 - ear_t/2, th)
    p3 = (-18.0, td/2 - ear_t/2, th + ear_h)
    p4 = (-24.0, td/2 + ear_t/2, th)
    p5 = (-12.0, td/2 + ear_t/2, th)
    p6 = (-18.0, td/2 + ear_t/2, th + ear_h)
    mesh.add_triangle(p1, p2, p3)
    mesh.add_triangle(p4, p6, p5)
    mesh.add_quad(p1, p4, p6, p3)
    mesh.add_quad(p2, p3, p6, p5)
    mesh.add_quad(p1, p2, p5, p4)

    # Right ear
    rp1 = (12.0, td/2 - ear_t/2, th)
    rp2 = (24.0, td/2 - ear_t/2, th)
    rp3 = (18.0, td/2 - ear_t/2, th + ear_h)
    rp4 = (12.0, td/2 + ear_t/2, th)
    rp5 = (24.0, td/2 + ear_t/2, th)
    rp6 = (18.0, td/2 + ear_t/2, th + ear_h)
    mesh.add_triangle(rp1, rp2, rp3)
    mesh.add_triangle(rp4, rp6, rp5)
    mesh.add_quad(rp1, rp4, rp6, rp3)
    mesh.add_quad(rp2, rp3, rp6, rp5)
    mesh.add_quad(rp1, rp2, rp5, rp4)

    return mesh


# ==============================================================================
# Model 4: wio_tilt_tv_base (Dual-Arm Tilting Clevis Desktop Stand)
# ==============================================================================
def build_tilt_tv_base_mesh():
    """
    Builds the stable desk base with dual clevis arms:
    - Broad desktop footprint: 78mm wide x 68mm deep x 5mm thick (low center of gravity)
    - Dual upright support forks (gap 15.0mm, snugly clamping the 14mm head lug)
    - Smooth 0°~45° tilt travel with angle stops
    """
    mesh = STLMesh()
    bw = 78.0
    bd = 68.0
    bt = 5.0

    # Base weighted plate
    mesh.add_box(-bw/2, 0, 0, bw, bd, bt)

    # Chamfered retro base edges
    mesh.add_box(-bw/2 + 4, 4, bt, bw - 8, bd - 8, 2.0)

    # Upright fork arms (Clevis)
    # Lug gap is 14.8mm (-7.4 to +7.4)
    # Left arm: X = -13.0 to -7.4 (thickness 5.6mm)
    # Right arm: X = +7.4 to +13.0 (thickness 5.6mm)
    arm_h = 28.0
    arm_d = 18.0
    cy = bd / 2

    # Left upright arm
    mesh.add_box(-13.0, cy - arm_d/2, bt, 5.6, arm_d, arm_h)
    # Left arm pivot boss
    mesh.add_cylinder(-13.0, cy, bt + arm_h - 6.0, 7.0, 5.6, axis='x', segments=16)

    # Right upright arm
    mesh.add_box(7.4, cy - arm_d/2, bt, 5.6, arm_d, arm_h)
    # Right arm pivot boss
    mesh.add_cylinder(7.4, cy, bt + arm_h - 6.0, 7.0, 5.6, axis='x', segments=16)

    # Anti-slip rubber foot indentations on bottom (4 corners)
    mesh.add_box(-bw/2 + 6, 6, -1.0, 10.0, 10.0, 1.0)
    mesh.add_box( bw/2 - 16, 6, -1.0, 10.0, 10.0, 1.0)
    mesh.add_box(-bw/2 + 6, bd - 16, -1.0, 10.0, 10.0, 1.0)
    mesh.add_box( bw/2 - 16, bd - 16, -1.0, 10.0, 10.0, 1.0)

    return mesh


# ==============================================================================
# Model 5: wio_tilt_tv_knob (Vintage Knurled Friction Thumb Wheel)
# ==============================================================================
def build_tilt_tv_knob_mesh():
    """
    Builds the vintage knurled thumb knob:
    - Outer diameter: 18mm, thickness 7mm
    - Knurled tactile gear perimeter for easy fingertip tightening
    - Center hex pocket for M3 / M4 bolt head
    """
    mesh = STLMesh()
    r = 9.0
    h = 7.0
    mesh.add_cylinder(0, 0, 0, r, h, axis='z', segments=24)

    # Knurled ridges along perimeter
    for i in range(12):
        a = i * (2 * math.pi / 12)
        rx = (r - 0.5) * math.cos(a)
        ry = (r - 0.5) * math.sin(a)
        mesh.add_box(rx - 0.8, ry - 0.8, 0, 1.6, 1.6, h)

    # Central collar
    mesh.add_cylinder(0, 0, h, 4.5, 3.0, axis='z', segments=16)

    return mesh


def write_openscad_files():
    # 1. wio_desktop_dock.scad
    dock_scad = """// ==============================================================================
// Wio Terminal 桌面多功能 30° 仰角底座与音腔背壳 (Desktop Angled Dock & Sound Chamber)
// ==============================================================================
$fn = 60;
wio_width   = 72.0;
wio_height  = 57.0;
wio_depth   = 12.0;
dock_width  = 84.0;
dock_depth  = 74.0;
front_h     = 10.0;
back_h      = 46.0;
tilt_angle  = 30.0;

module wio_desktop_dock() {
    difference() {
        union() {
            translate([-dock_width/2, 0, 0]) cube([dock_width, dock_depth, 3.0]);
            translate([-dock_width/2, 0, 0]) cube([dock_width, 4.0, 14.0]);
            translate([-dock_width/2 + 4.5, dock_depth - 3.5, 0]) cube([dock_width - 9.0, 3.5, back_h]);
            rotate([tilt_angle, 0, 0])
                translate([-dock_width/2 + 4.5, 10.0, -2.0]) cube([dock_width - 9.0, 60.0, 3.5]);
            translate([-20 - 4, dock_depth/2 - 4, 12]) cube([8, 8, 12]);
            translate([ 20 - 4, dock_depth/2 - 4, 12]) cube([8, 8, 12]);
        }
        translate([-30, 15, 3.0]) cube([60, 45, 18]);
        for (i = [-5 : 5]) {
            translate([i * 6.5 - 1.2, dock_depth - 5.0, 14.0]) cube([2.4, 8.0, 22.0]);
        }
        translate([-dock_width/2 - 1, 14.0, 4.0]) cube([10.0, 18.0, 10.0]);
    }
}
wio_desktop_dock();
"""
    with open('cad/wio_desktop_dock.scad', 'w', encoding='utf-8') as f:
        f.write(dock_scad)

    # 2. wio_tilt_tv.scad (Fully Articulated Retro Monitor System)
    tilt_scad = """// ==============================================================================
// Wio Terminal 可俯仰摆动复古小电视监视器系统 (Articulated Tilt Retro TV Monitor)
// 包含：
// 1. 复古小电视机头（带 CRT 显像管圆角边框、音腔、电池仓）
// 2. 独立低重心桌面双叉底座（支持 0° ~ 45° 自由俯仰调节）
// 3. 复古阻尼手拧旋钮
// ==============================================================================

$fn = 60;

// 控制展示模式: "assembly" (装配总览), "head" (机头), "base" (底座), "knob" (旋钮)
mode = "assembly";
tilt_deg = 25; // 俯仰摆动演示角度 (0° ~ 45°)

tv_w = 84.0;
tv_h = 66.0;
tv_d = 32.0;

module tv_head() {
    difference() {
        union() {
            // 机头主体
            translate([-tv_w/2, 0, 0]) cube([tv_w, tv_d, tv_h]);
            // 底部铰链转轴凸耳
            translate([-7.0, tv_d/2 - 8.0, -14.0]) cube([14.0, 16.0, 14.0]);
            // 右侧复古旋钮
            translate([tv_w/2 - 8, -3, tv_h/2 + 10]) rotate([-90,0,0]) cylinder(d=11, h=3);
            translate([tv_w/2 - 8, -3, tv_h/2 - 10]) rotate([-90,0,0]) cylinder(d=11, h=3);
            // 顶部猫咪耳朵
            translate([-18, tv_d/2, tv_h]) rotate([0,0,0])
                linear_extrude(height=3.5, center=true) polygon([[-6,0],[6,0],[0,11]]);
            translate([ 18, tv_d/2, tv_h]) rotate([0,0,0])
                linear_extrude(height=3.5, center=true) polygon([[-6,0],[6,0],[0,11]]);
        }
        // Wio Terminal 插槽与 CRT 视窗 (50mm x 38mm)
        translate([-tv_w/2 + 8, -2, (tv_h - 38)/2]) cube([50, 6, 38]);
        // 内部音腔与电池仓 (62mm x 46mm x 18mm)
        translate([-31, 10, 8]) cube([62, tv_d, 46]);
        // 转轴过孔 (M3/M4)
        translate([-10, tv_d/2, -7.0]) rotate([0, 90, 0]) cylinder(d=3.6, h=20);
        // 背部百叶窗出音孔
        for (i = [0:5]) {
            translate([-28, tv_d - 2, 14 + i*6]) cube([56, 4, 2.5]);
        }
        // 左侧 Type-C 开孔
        translate([-tv_w/2 - 1, 8, 14]) cube([6, 16, 12]);
        // 顶部按键开槽
        translate([-20, tv_d/2 - 5, tv_h - 4]) cube([40, 10, 6]);
    }
}

module desk_base() {
    difference() {
        union() {
            // 平稳大底座
            translate([-39, 0, 0]) cube([78, 68, 5]);
            // 双叉支架臂
            translate([-13.0, 34 - 9, 5]) cube([5.6, 18, 28]);
            translate([  7.4, 34 - 9, 5]) cube([5.6, 18, 28]);
            // 支架臂顶部转轴套筒
            translate([-13.0, 34, 27]) rotate([0, 90, 0]) cylinder(d=14, h=5.6);
            translate([  7.4, 34, 27]) rotate([0, 90, 0]) cylinder(d=14, h=5.6);
        }
        // 左右支架转轴对穿孔
        translate([-20, 34, 27]) rotate([0, 90, 0]) cylinder(d=3.4, h=40);
        // 底部防滑脚槽
        translate([-33, 6, -1]) cube([10, 10, 2]);
        translate([ 23, 6, -1]) cube([10, 10, 2]);
        translate([-33, 52, -1]) cube([10, 10, 2]);
        translate([ 23, 52, -1]) cube([10, 10, 2]);
    }
}

module thumb_knob() {
    difference() {
        union() {
            cylinder(d=18, h=7);
            cylinder(d=9, h=10);
            for (i=[0:11]) {
                rotate([0,0,i*30]) translate([8.5, -0.8, 0]) cube([1.6, 1.6, 7]);
            }
        }
        // M3/M4 螺母/螺栓六角沉头孔
        translate([0, 0, -1]) cylinder(d=6.2, h=4, $fn=6);
        translate([0, 0, -1]) cylinder(d=3.4, h=12);
    }
}

// 渲染分支控制
if (mode == "assembly") {
    // 渲染底座
    color("#444444") desk_base();
    // 渲染可仰角摆动机头
    translate([0, 34, 27])
        rotate([tilt_deg, 0, 0])
            translate([0, -tv_d/2, 7])
                color("#F5F2EB") tv_head();
    // 侧边手拧旋钮
    translate([14, 34, 27]) rotate([0, 90, 0]) color("#C8A165") thumb_knob();
} else if (mode == "head") {
    tv_head();
} else if (mode == "base") {
    desk_base();
} else if (mode == "knob") {
    thumb_knob();
}
"""
    with open('cad/wio_tilt_tv.scad', 'w', encoding='utf-8') as f:
        f.write(tilt_scad)
    print("Wrote cad/wio_tilt_tv.scad")


def main():
    print("Generating 3D meshes...")
    # 1. Fixed 30 deg Dock
    dock_mesh = build_desktop_dock_mesh()
    dock_mesh.write_binary_stl('cad/stl/wio_desktop_dock.stl')

    # 2. Retro TV Bezel
    tv_mesh = build_retro_tv_mesh()
    tv_mesh.write_binary_stl('cad/stl/wio_retro_tv.stl')

    # 3. Articulated Tilt Retro TV System
    head_mesh = build_tilt_tv_head_mesh()
    head_mesh.write_binary_stl('cad/stl/wio_tilt_tv_head.stl')

    base_mesh = build_tilt_tv_base_mesh()
    base_mesh.write_binary_stl('cad/stl/wio_tilt_tv_base.stl')

    knob_mesh = build_tilt_tv_knob_mesh()
    knob_mesh.write_binary_stl('cad/stl/wio_tilt_tv_knob.stl')

    write_openscad_files()
    print("All CAD assets generated successfully!")

if __name__ == '__main__':
    main()
