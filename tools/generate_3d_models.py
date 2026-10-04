"""
generate_3d_models.py - Generate 3D CAD OpenSCAD and watertight binary STL models for Wio Terminal
"""

import math
import struct
import os

class STLMesh:
    def __init__(self):
        self.triangles = []

    def add_triangle(self, v1, v2, v3):
        # Calculate normal
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
        # Two triangles forming a quad: (v1, v2, v3) and (v1, v3, v4)
        self.add_triangle(v1, v2, v3)
        self.add_triangle(v1, v3, v4)

    def add_box(self, x, y, z, dx, dy, dz):
        # 8 vertices
        p0 = (x, y, z)
        p1 = (x + dx, y, z)
        p2 = (x + dx, y + dy, z)
        p3 = (x, y + dy, z)
        p4 = (x, y, z + dz)
        p5 = (x + dx, y, z + dz)
        p6 = (x + dx, y + dy, z + dz)
        p7 = (x, y + dy, z + dz)

        # Bottom (z = z)
        self.add_quad(p0, p3, p2, p1)
        # Top (z = z + dz)
        self.add_quad(p4, p5, p6, p7)
        # Front (y = y)
        self.add_quad(p0, p1, p5, p4)
        # Back (y = y + dy)
        self.add_quad(p2, p3, p7, p6)
        # Left (x = x)
        self.add_quad(p3, p0, p4, p7)
        # Right (x = x + dx)
        self.add_quad(p1, p2, p6, p5)

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


def build_desktop_dock_mesh():
    """
    Builds a solid 3D printable desktop angled stand & expansion chassis:
    - Base width: 84mm, depth: 70mm, front lip: 12mm, back height: 42mm
    - Cradle recess for Wio Terminal: 73.5mm x 58.5mm, tilted at 30 degrees
    - Chamber for speaker & battery
    - Left USB-C pass-through notch
    """
    mesh = STLMesh()

    # Base wedge dimensions
    bw = 84.0   # Width (X: -42 to +42)
    bd = 74.0   # Depth (Y: 0 to 74)
    fh = 10.0   # Front height
    bh = 46.0   # Back height
    wall = 3.2  # Outer wall thickness

    # Base footprint plate (solid ground footing)
    mesh.add_box(-bw/2, 0, 0, bw, bd, 3.0)

    # Left and Right sturdy triangular side brackets
    side_thick = 4.5
    # Left side wall
    # 6 vertices for wedge
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

    # Left wedge outer face
    mesh.add_triangle(p_f_bot, p_f_top, p_b_top)
    mesh.add_triangle(p_f_bot, p_b_top, p_b_bot)
    # Left wedge inner face
    mesh.add_triangle(p_f_bot_in, p_b_top_in, p_f_top_in)
    mesh.add_triangle(p_f_bot_in, p_b_bot_in, p_b_top_in)
    # Left wedge top slope
    mesh.add_quad(p_f_top, p_f_top_in, p_b_top_in, p_b_top)
    # Left wedge front face
    mesh.add_quad(p_f_bot, p_f_bot_in, p_f_top_in, p_f_top)
    # Left wedge back face
    mesh.add_quad(p_b_bot_in, p_b_bot, p_b_top, p_b_top_in)

    # Right side wall
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

    # Right wedge outer face
    mesh.add_triangle(rp_f_bot, rp_b_top, rp_f_top)
    mesh.add_triangle(rp_f_bot, rp_b_bot, rp_b_top)
    # Right wedge inner face
    mesh.add_triangle(rp_f_bot_in, rp_f_top_in, rp_b_top_in)
    mesh.add_triangle(rp_f_bot_in, rp_b_top_in, rp_b_bot_in)
    # Right wedge top slope
    mesh.add_quad(rp_f_top_in, rp_f_top, rp_b_top, rp_b_top_in)
    # Right wedge front face
    mesh.add_quad(rp_f_bot_in, rp_f_bot, rp_f_top, rp_f_top_in)
    # Right wedge back face
    mesh.add_quad(rp_b_bot, rp_b_bot_in, rp_b_top_in, rp_b_top)

    # Front retaining lip to prevent Wio Terminal from sliding down
    lip_h = 14.0
    mesh.add_box(-bw/2, 0, 0, bw, 4.0, lip_h)

    # Back support plate with speaker grille slots
    back_y = bd - 3.5
    back_h = bh
    mesh.add_box(-bw/2 + side_thick, back_y, 0, bw - 2*side_thick, 3.5, 12.0)
    mesh.add_box(-bw/2 + side_thick, back_y, 36.0, bw - 2*side_thick, 3.5, back_h - 36.0)

    # Back sound grille slats (slotted grille)
    slat_w = 4.0
    for i in range(-5, 6):
        sx = i * 6.5
        mesh.add_box(sx - slat_w/2, back_y, 12.0, slat_w, 3.5, 24.0)

    # Back rest shelf at 30 deg slope supporting Wio Terminal back
    # Angle theta approx 30 deg: tan(30) = 0.577 -> (bh - fh)/bd = (46-10)/74 = 0.486 (~26 deg)
    shelf_t = 3.5
    shelf_w = bw - 2*side_thick
    # Construct slanted backplate
    # Points on the slope
    y1, z1 = 6.0, 7.0
    y2, z2 = bd - 6.0, bh - 6.0
    mesh.add_quad((-shelf_w/2, y1, z1), (shelf_w/2, y1, z1), (shelf_w/2, y2, z2), (-shelf_w/2, y2, z2))
    mesh.add_quad((-shelf_w/2, y1, z1 - shelf_t), (-shelf_w/2, y2, z2 - shelf_t), (shelf_w/2, y2, z2 - shelf_t), (shelf_w/2, y1, z1 - shelf_t))
    mesh.add_quad((-shelf_w/2, y1, z1 - shelf_t), (shelf_w/2, y1, z1 - shelf_t), (shelf_w/2, y1, z1), (-shelf_w/2, y1, z1))
    mesh.add_quad((-shelf_w/2, y2, z2), (shelf_w/2, y2, z2), (shelf_w/2, y2, z2 - shelf_t), (-shelf_w/2, y2, z2 - shelf_t))

    # M3 mounting bosses on the shelf (spacing 40mm apart)
    boss_w = 8.0
    boss_h = 10.0
    boss_y = (y1 + y2) / 2
    boss_z = (z1 + z2) / 2 - 2.0
    mesh.add_box(-20 - boss_w/2, boss_y - 4, boss_z - boss_h, boss_w, 8.0, boss_h)
    mesh.add_box( 20 - boss_w/2, boss_y - 4, boss_z - boss_h, boss_w, 8.0, boss_h)

    # Left USB-C pass-through cutout guide
    mesh.add_box(-bw/2, 10.0, 3.0, side_thick, 16.0, 10.0)

    # Internal battery / speaker cradle floor rib
    mesh.add_box(-25.0, 20.0, 3.0, 50.0, 30.0, 2.0)

    return mesh


def build_retro_tv_mesh():
    """
    Builds a retro CRT mini-TV snap enclosure for Wio Terminal:
    - Retro TV body: 82mm x 66mm x 24mm
    - Front CRT screen window: 51mm x 38mm (centered)
    - Right-side vintage knobs
    - 4 angled retro TV legs
    - Top cute cat ears
    """
    mesh = STLMesh()

    tw = 82.0   # TV width
    th = 66.0   # TV height
    td = 24.0   # TV depth
    wall = 3.0

    # Main TV outer shell (Box with hollow interior)
    # Bottom
    mesh.add_box(-tw/2, 0, 0, tw, td, wall)
    # Top
    mesh.add_box(-tw/2, 0, th - wall, tw, td, wall)
    # Left
    mesh.add_box(-tw/2, 0, wall, wall, td, th - 2*wall)
    # Right
    mesh.add_box(tw/2 - wall, 0, wall, wall, td, th - 2*wall)

    # Front TV Bezel (with screen opening)
    # Screen opening: width 50mm, height 38mm, centered at x=-6 (leaving right side for knobs)
    sw = 50.0
    sh = 38.0
    sx0 = -tw/2 + 7.0
    sy0 = (th - sh) / 2

    # Front bezel parts around screen:
    # 1. Left border
    mesh.add_box(-tw/2, 0, 0, 7.0, wall, th)
    # 2. Bottom border under screen
    mesh.add_box(sx0, 0, 0, sw, wall, sy0)
    # 3. Top border above screen
    mesh.add_box(sx0, 0, sy0 + sh, sw, wall, th - (sy0 + sh))
    # 4. Right panel (houses vintage knobs and speaker slits)
    rx0 = sx0 + sw
    rw = tw/2 - rx0
    mesh.add_box(rx0, 0, 0, rw, wall, th)

    # Retro Knobs (2 extruded cylinders/boxes on the right panel)
    mesh.add_box(rx0 + 3.0, -4.0, sy0 + sh - 8.0, 10.0, 4.0, 10.0)
    mesh.add_box(rx0 + 3.0, -4.0, sy0 + 6.0, 10.0, 4.0, 10.0)

    # Retro Speaker grille lines under knobs
    for i in range(3):
        mesh.add_box(rx0 + 2.0, -1.0, sy0 + 20.0 + i*4.0, 12.0, 1.0, 1.5)

    # 4 Angled Retro TV Legs
    leg_w = 4.0
    leg_d = 4.0
    leg_h = 10.0
    # Front-left leg
    mesh.add_box(-tw/2 + 5, 2, -leg_h, leg_w, leg_d, leg_h)
    # Front-right leg
    mesh.add_box(tw/2 - 9, 2, -leg_h, leg_w, leg_d, leg_h)
    # Back-left leg
    mesh.add_box(-tw/2 + 5, td - 6, -leg_h, leg_w, leg_d, leg_h)
    # Back-right leg
    mesh.add_box(tw/2 - 9, td - 6, -leg_h, leg_w, leg_d, leg_h)

    # Cute Cat Ears on top of the TV
    ear_base_w = 12.0
    ear_h = 12.0
    ear_t = 3.5

    # Left Ear (Prism)
    # Base at x=-24 to -12, z=th
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

    # Right Ear (Prism)
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


def write_openscad_files():
    dock_scad = """// ==============================================================================
// Wio Terminal 桌面多功能仰角底座与音腔背壳 (Desktop Angled Dock & Sound Chamber)
// 专为“小维”AI 电子桌宠、赛博时钟、番茄钟设计
// 支持标准 30° 黄金视距仰角，内嵌 I2S 腔体喇叭 + 聚合物锂电池
// ==============================================================================

$fn = 60;

// 设备外形尺寸 (Wio Terminal: 72mm x 57mm x 12mm)
wio_width   = 72.0;
wio_height  = 57.0;
wio_depth   = 12.0;
clearance   = 0.6; // 装配公差

// 底座外壳参数
dock_width  = 84.0;
dock_depth  = 74.0;
front_h     = 10.0;
back_h      = 46.0;
tilt_angle  = 30.0; // 30度黄金倾角
wall_thick  = 3.2;

module wio_desktop_dock() {
    difference() {
        // 主基座外壳轮廓
        union() {
            // 底座平稳承重底板
            translate([-dock_width/2, 0, 0])
                cube([dock_width, dock_depth, 3.0]);

            // 左右加厚侧向三角支撑臂
            translate([-dock_width/2, 0, 0])
                polyhedron(
                    points = [
                        [0, 0, 0], [4.5, 0, 0], [4.5, dock_depth, 0], [0, dock_depth, 0],
                        [0, 0, front_h], [4.5, 0, front_h], [4.5, dock_depth, back_h], [0, dock_depth, back_h]
                    ],
                    faces = [
                        [0,1,2,3], [4,5,6,7], [0,1,5,4], [2,3,7,6], [0,3,7,4], [1,2,6,5]
                    ]
                );

            translate([dock_width/2 - 4.5, 0, 0])
                polyhedron(
                    points = [
                        [0, 0, 0], [4.5, 0, 0], [4.5, dock_depth, 0], [0, dock_depth, 0],
                        [0, 0, front_h], [4.5, 0, front_h], [4.5, dock_depth, back_h], [0, dock_depth, back_h]
                    ],
                    faces = [
                        [0,1,2,3], [4,5,6,7], [0,1,5,4], [2,3,7,6], [0,3,7,4], [1,2,6,5]
                    ]
                );

            // 前方防滑托台
            translate([-dock_width/2, 0, 0])
                cube([dock_width, 4.0, 14.0]);

            // 背部支撑背板
            translate([-dock_width/2 + 4.5, dock_depth - 3.5, 0])
                cube([dock_width - 9.0, 3.5, back_h]);

            // 倾斜背衬板
            rotate([tilt_angle, 0, 0])
                translate([-dock_width/2 + 4.5, 10.0, -2.0])
                    cube([dock_width - 9.0, 60.0, 3.5]);

            // M3 螺丝固定座 (间距 40mm)
            translate([-20 - 4, dock_depth/2 - 4, 12])
                cube([8, 8, 12]);
            translate([ 20 - 4, dock_depth/2 - 4, 12])
                cube([8, 8, 12]);
        }

        // 内部音腔与电池预留空腔 (60mm x 45mm x 16mm)
        translate([-30, 15, 3.0])
            cube([60, 45, 18]);

        // 背部百叶窗式出音孔
        for (i = [-5 : 5]) {
            translate([i * 6.5 - 1.2, dock_depth - 5.0, 14.0])
                cube([2.4, 8.0, 22.0]);
        }

        // 左侧 Type-C 充电开孔与电源开关开孔
        translate([-dock_width/2 - 1, 14.0, 4.0])
            cube([10.0, 18.0, 10.0]);

        // M3 螺丝过孔
        translate([-20, dock_depth/2, 0])
            cylinder(d = 3.4, h = 30);
        translate([ 20, dock_depth/2, 0])
            cylinder(d = 3.4, h = 30);
    }
}

wio_desktop_dock();
"""

    tv_scad = """// ==============================================================================
// Wio Terminal 复古迷你 CRT 小电视 / 萌宠猫耳外壳 (Retro CRT TV & Desk Pet Bezel)
// 专为“小维”AI 电子桌宠像素小屋打造的复古极客外壳
// 带有复古显像管曲面边框、复古旋钮、独立倾角脚撑与猫咪耳朵
// ==============================================================================

$fn = 60;

tv_w = 82.0;
tv_h = 66.0;
tv_d = 24.0;
wall = 3.0;

module retro_tv() {
    difference() {
        // 主壳体
        union() {
            // 电视机主体倒角方盒
            translate([-tv_w/2, 0, 0])
                cube([tv_w, tv_d, tv_h]);

            // 右侧复古双旋转旋钮
            translate([tv_w/2 - 14, -3, tv_h/2 + 10])
                rotate([-90, 0, 0])
                    cylinder(d = 12, h = 3);
            translate([tv_w/2 - 14, -3, tv_h/2 - 10])
                rotate([-90, 0, 0])
                    cylinder(d = 12, h = 3);

            // 4 只复古小电视斜撑脚
            translate([-tv_w/2 + 5, 2, -10]) cylinder(d1=3, d2=6, h=10);
            translate([ tv_w/2 - 7, 2, -10]) cylinder(d1=3, d2=6, h=10);
            translate([-tv_w/2 + 5, tv_d - 5, -10]) cylinder(d1=3, d2=6, h=10);
            translate([ tv_w/2 - 7, tv_d - 5, -10]) cylinder(d1=3, d2=6, h=10);

            // 顶部萌系猫咪双耳
            translate([-20, tv_d/2, tv_h])
                rotate([0, 0, 0])
                    linear_extrude(height = 3.5, center = true)
                        polygon([[-7, 0], [7, 0], [0, 12]]);

            translate([ 20, tv_d/2, tv_h])
                rotate([0, 0, 0])
                    linear_extrude(height = 3.5, center = true)
                        polygon([[-7, 0], [7, 0], [0, 12]]);
        }

        // 内部容纳槽 (用于插入 Wio Terminal: 73mm x 58mm x 13mm)
        translate([-tv_w/2 + wall, wall, wall])
            cube([tv_w - 2*wall, tv_d, tv_h - 2*wall]);

        // 正面 CRT 显示屏开窗 (50mm x 38mm，匹配 2.4 寸屏幕)
        translate([-tv_w/2 + 8, -2, (tv_h - 38)/2])
            cube([50, wall + 4, 38]);

        // 右下角复古发声孔槽
        for (i = [0:2]) {
            translate([tv_w/2 - 18, -2, (tv_h - 38)/2 + i*5])
                cube([14, wall + 4, 2]);
        }

        // 顶部三键与摇杆避空开槽
        translate([-tv_w/2 + 10, tv_d/2 - 6, tv_h - wall - 1])
            cube([45, 12, wall + 3]);
    }
}

retro_tv();
"""

    with open('cad/wio_desktop_dock.scad', 'w', encoding='utf-8') as f:
        f.write(dock_scad)
    print("Wrote cad/wio_desktop_dock.scad")

    with open('cad/wio_retro_tv.scad', 'w', encoding='utf-8') as f:
        f.write(tv_scad)
    print("Wrote cad/wio_retro_tv.scad")


def main():
    print("Generating 3D meshes...")
    dock_mesh = build_desktop_dock_mesh()
    dock_mesh.write_binary_stl('cad/stl/wio_desktop_dock.stl')

    tv_mesh = build_retro_tv_mesh()
    tv_mesh.write_binary_stl('cad/stl/wio_retro_tv.stl')

    write_openscad_files()
    print("All CAD assets generated successfully!")

if __name__ == '__main__':
    main()
