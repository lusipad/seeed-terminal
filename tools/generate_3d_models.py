"""
generate_3d_models.py - Parametric CAD generator for the Wio Terminal retro desktop monitor.

A retro CRT-style monitor (holds the Wio Terminal) sitting on a hollow "computer box" base,
in the spirit of retro mini-PC monitors. Uses the manifold3d CSG engine so every STL is a
watertight single shell.

Parts (cad/stl/):
  wio_tilt_tv_head.stl          monitor front shell; Wio slides in from the back
  wio_tilt_tv_rear_cover.stl    CRT "tube" rear cover; its U-lip retains the Wio
  wio_tilt_tv_base.stl          hollow computer box: hinge, speaker bay, vents, panel slot
  wio_tilt_tv_bottom_cover.stl  screw-on bottom: battery bay, module standoffs, foot pads
  wio_tilt_tv_front_panel.stl   slide-in front panel with port cut-outs (swap to customise)
  wio_tilt_tv_knob.stl          hinge friction knob (captive M3 nut)

Tilt: the monitor hinges about an axis behind and below its rear edge (HEAD_AXIS / BASE_AXIS),
so tilting back (0-45 deg) only ever lifts the monitor away from the base.
Wio Terminal bottom-edge ports (USB-C, 2x Grove) and 40-pin wiring drop through openings in
the monitor floor straight into the base.
"""

import os

import numpy as np
import trimesh

rot_x90 = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
rot_y90 = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])

# Hinge axis (parallel to X) in head and base coordinates. Assembly maps one onto the other.
HEAD_AXIS = (0.0, 46.0, -3.0)
BASE_AXIS = (0.0, 0.0, 26.3)

# Base box
BASE_W, BASE_Y0, BASE_Y1 = 94.0, -60.0, 10.0      # width, front / rear Y
BASE_TOP, STEP_Y, STEP_TOP = 30.0, -8.0, 20.0     # main top, rear-step start Y, rear-step top
BASE_Z0 = 2.0                                     # bottom cover occupies Z 0..2
WALL = 2.2
HINGE_BAY_X = 38.0                                 # rear hinge bay spans |X| < 38 (full-height side rails outside)
BOSS_XY = [(sx * 41.5, BASE_Y0 + 9.0) for sx in (-1, 1)] + [(sx * 42.0, BASE_Y1 - 5.5) for sx in (-1, 1)]
PANEL_Y = (BASE_Y0 + WALL, BASE_Y0 + WALL + 2.0)  # front panel slot (behind the front wall)


def rounded_slab_y(w, h, r, y0, y1, cx=0.0, cz=0.0, sections=48):
    """Rounded rectangle (w along X, h along Z, corner radius r) extruded along Y from y0 to y1."""
    cyls = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = trimesh.creation.cylinder(radius=r, height=y1 - y0, sections=sections)
            c.apply_transform(rot_x90)
            c.apply_translation([cx + sx * (w / 2 - r), (y0 + y1) / 2, cz + sz * (h / 2 - r)])
            cyls.append(c)
    return trimesh.util.concatenate(cyls)


def rounded_slab_z(w, d, r, z0, z1, cx=0.0, cy=0.0, sections=48):
    """Rounded rectangle (w along X, d along Y, corner radius r) extruded along Z from z0 to z1."""
    cyls = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = trimesh.creation.cylinder(radius=r, height=z1 - z0, sections=sections)
            c.apply_translation([cx + sx * (w / 2 - r), cy + sy * (d / 2 - r), (z0 + z1) / 2])
            cyls.append(c)
    return trimesh.util.concatenate(cyls)


def rounded_slab_x(d, h, r, x0, x1, cy=0.0, cz=0.0, sections=32):
    """Rounded rectangle (d along Y, h along Z, corner radius r) extruded along X from x0 to x1."""
    cyls = []
    for sy in (-1, 1):
        for sz in (-1, 1):
            c = trimesh.creation.cylinder(radius=r, height=x1 - x0, sections=sections)
            c.apply_transform(rot_y90)
            c.apply_translation([(x0 + x1) / 2, cy + sy * (d / 2 - r), cz + sz * (h / 2 - r)])
            cyls.append(c)
    return trimesh.util.concatenate(cyls)


def hull(*parts):
    return trimesh.util.concatenate(list(parts)).convex_hull


def box(lo, hi):
    return trimesh.creation.box(bounds=[lo, hi])


def x_cylinder(radius, x0, x1, y, z, sections=48):
    c = trimesh.creation.cylinder(radius=radius, height=x1 - x0, sections=sections)
    c.apply_transform(rot_y90)
    c.apply_translation([(x0 + x1) / 2, y, z])
    return c


def y_cylinder(radius, y0, y1, x, z, sections=48):
    c = trimesh.creation.cylinder(radius=radius, height=y1 - y0, sections=sections)
    c.apply_transform(rot_x90)
    c.apply_translation([x, (y0 + y1) / 2, z])
    return c


def union(parts):
    return trimesh.boolean.union(parts, engine='manifold')


def cut(mesh, parts):
    return mesh.difference(parts, engine='manifold')


# ==============================================================================
# Part 1: monitor front shell (head)
# Front bezel 82 x 63 (R9) stepping down to a 79 x 62 (R6) body; flat bottom at Z=1
# ==============================================================================
def build_tilt_tv_head(top_load=False):
    # Front bezel lip: 82.0 x 63.0, corner R9, Y in [0, 3], Z in [1, 64]
    bezel = hull(rounded_slab_y(82.0, 63.0, 9.0, 0.0, 3.0, cz=32.5))
    # Body: 79.0 x 62.0, corner R6, Y in [2, 26], Z in [1, 63]
    # Walls around the 73 x 58 pocket: 3.0 at the sides, 2.0 top/bottom
    body = hull(rounded_slab_y(79.0, 62.0, 6.0, 2.0, 26.0, cz=32.0))

    # Front right retro dials with a raised pointer line
    deco = []
    for dz in (46.0, 32.0):
        deco.append(y_cylinder(4.5, -2.2, 0.0, 29.0, dz))
        tick = box([28.55, -3.1, dz - 0.1], [29.45, -2.1, dz + 3.3])
        deco.append(tick)
    # Red / green / blue indicator dots, top right of the bezel
    for i in range(3):
        deco.append(y_cylinder(0.8, -0.6, 0.2, 26.5 + 2.5 * i, 57.5, sections=24))

    # Hinge tail: 12mm bar under the rear of the monitor ending in the knuckle on HEAD_AXIS.
    # Its top stays at Z<=1.5 behind the body so the rear cover clears it.
    ay, az = HEAD_AXIS[1], HEAD_AXIS[2]
    tail = hull(box([-6.0, 16.0, -1.5], [6.0, 26.0, 1.4]),
                x_cylinder(4.5, -6.0, 6.0, ay, az))

    shell = union([bezel, body, tail] + deco)

    # 1. Screen window 50 x 38, R2.5 corners, 1.2mm CRT chamfer on the left/top/bottom edges
    #    (the right edge sits 1.0mm from the joystick hole, so it stays square)
    win_core = hull(rounded_slab_y(50.0, 38.0, 2.5, -1.0, 6.0, cx=-5.0, cz=32.0))
    win_chamfer = hull(rounded_slab_y(51.2, 40.4, 3.7, -1.0, -0.01, cx=-5.6, cz=32.0),
                       rounded_slab_y(50.0, 38.0, 2.5, 1.19, 1.2, cx=-5.0, cz=32.0))
    # 2. Joystick opening D12 (1.0mm web to the window)
    joystick = y_cylinder(6.0, -4.0, 4.0, 27.0, 16.0)
    # 3. Rear slide-in pocket 73 x 58 R3; Wio (72 x 57 x 12) stops against the 2.2mm front wall
    pocket = hull(rounded_slab_y(73.0, 58.0, 3.0, 2.2, 30.0, cz=32.0))
    # 4. Top 3-button finger slot 42 x 8
    top_btns = box([-26.0, 4.5, 58.0], [16.0, 12.5, 68.0])
    if top_load:
        # JLC one-piece monitor: the Wio drops in from the top through a full-width slot,
        # which also leaves its three top buttons exposed
        # (cut down to Z61 across the full width so the R6 body corners leave no knife edge)
        # The pocket's upper corners are squared off so the Wio's lower corners pass on the way in
        top_btns = union([box([-41.5, 2.2, 61.0], [41.5, 14.5, 70.0]), box([-36.5, 2.2, 32.0], [36.5, 14.5, 61.5])])
    # 5. Left side access window 14 x 10 (side switch)
    side_win = box([-45.0, 1.5, 27.0], [-35.0, 15.5, 37.0])
    # 6. Floor slot under the Wio bottom edge (USB-C + 2x Grove plug straight down into the base)
    port_slot = box([-31.0, 3.0, -2.0], [31.0, 14.0, 4.0])
    # 7. Floor wire holes behind the Wio (40-pin header jumpers), clear of the hinge tail
    wire_holes = [box([-32.0, 16.0, -2.0], [-12.0, 24.0, 4.0]), box([12.0, 16.0, -2.0], [32.0, 24.0, 4.0])]
    # 8. Hinge bore D3.4 and a top groove that hollows the tail (drains up into the cover space)
    bore = x_cylinder(1.7, -10.0, 10.0, ay, az, sections=32)
    # (top_load: the fused cover sits just above the tail, so the groove stops at Z1.7 - it still
    #  opens into the air gap under the cover but leaves no thin web below the cover)
    gt = 1.7 if top_load else 4.6
    tail_core = hull(box([-3.5, 18.0, 0.4], [3.5, 18.1, gt]), box([-3.5, 41.9, -4.5], [3.5, 42.0, gt]))
    # 9. Retro side vent grooves (1.0mm deep, both sides, rear half)
    vents = []
    for sx in (-1, 1):
        for i in range(7):
            v = hull(rounded_slab_z(2.0, 6.0, 0.8, 0.0, 1.6))
            v.apply_translation([sx * 39.5, 20.5, 19.2 + i * 4.0])
            vents.append(v)

    return cut(shell, [win_core, win_chamfer, joystick, pocket, top_btns, side_win, port_slot, bore,
                       tail_core] + wire_holes + vents)


# ==============================================================================
# Part 2: CRT rear cover. Friction-fits into the pocket; its U-lip (top + sides, open at the
# bottom so the floor wire holes stay clear) pushes the Wio against the front wall.
# ==============================================================================
def build_rear_cover(fused=False):
    y0 = 25.6 if fused else 26.0          # fused: overlap the body's back face by 0.4mm
    outer = hull(rounded_slab_y(79.0, 61.0, 6.0, y0, y0 + 0.4, cz=32.5),
                 rounded_slab_y(58.0, 42.0, 9.0, 41.6, 42.0, cz=34.0))
    inner = hull(rounded_slab_y(75.0, 57.0, 4.0, y0 - 0.1, y0 + 0.5, cz=32.5),
                 rounded_slab_y(54.0, 38.0, 7.0, 39.6, 40.0, cz=34.0))
    shell = cut(outer, [inner])
    slots = [hull(rounded_slab_y(1.8, 16.0, 0.85, 38.0, 43.0, cx=-13.5 + 4.5 * i, cz=36.0)) for i in range(7)]
    if fused:
        return cut(shell, slots)

    lip_o = hull(rounded_slab_y(72.6, 57.6, 2.8, 14.8, 26.2, cz=32.0))
    lip_i = hull(rounded_slab_y(69.4, 54.4, 1.2, 14.0, 28.5, cz=32.0))
    lip = cut(lip_o, [lip_i, box([-40, 14.0, 0.0], [40, 27.0, 9.0])])

    # Flange joining the lip to the shell, just behind the body's back face
    flange = cut(hull(rounded_slab_y(77.0, 59.0, 5.0, 26.0, 27.8, cz=32.5)), [lip_i])
    cover = union([shell, lip, flange])
    return cut(cover, slots)


# ==============================================================================
# Part 3: computer box base (hollow, open bottom closed by the bottom cover)
# ==============================================================================
def build_tilt_tv_base(jlc=False):
    """jlc=True: one-piece variant for JLC free printing - walls run down to the desk (no bottom
    cover), the ports are cut straight into the front wall (no panel), no cover bosses."""
    D = BASE_Y1 - BASE_Y0
    cy = (BASE_Y0 + BASE_Y1) / 2
    z0 = 0.0 if jlc else BASE_Z0
    # Box with a rear hinge bay cut into the middle; the side rails stay full height so the
    # box reads as a clean block from the sides
    outer = cut(hull(rounded_slab_z(BASE_W, D, 6.0, z0, BASE_TOP, cy=cy)),
                [box([-HINGE_BAY_X, STEP_Y, STEP_TOP], [HINGE_BAY_X, BASE_Y1 + 1.0, BASE_TOP + 1.0])])
    inner = cut(hull(rounded_slab_z(BASE_W - 2 * WALL, D - 2 * WALL, 6.0 - WALL, z0 - 1.0, BASE_TOP - WALL, cy=cy)),
                [box([-HINGE_BAY_X - WALL, STEP_Y - WALL, STEP_TOP - WALL], [HINGE_BAY_X + WALL, BASE_Y1 + 1.0, BASE_TOP + 1.0])])
    shell = cut(outer, [inner])

    adds = []
    if not jlc:
        # Corner screw bosses for the bottom cover (D7, M3 self-tap pilot D2.5)
        for bx, by in BOSS_XY:
            r = 3.5 if by < STEP_Y else 3.0
            c = trimesh.creation.cylinder(radius=r, height=BASE_TOP - BASE_Z0 - 0.5)
            c.apply_translation([bx, by, (BASE_Z0 + BASE_TOP - 0.5) / 2])
            adds.append(c)
        # Front panel retaining ribs (panel slides up between the front wall and these ribs)
        for sx in (-1, 1):
            x0, x1 = sorted([sx * 37.0, sx * (BASE_W / 2 - WALL + 0.1)])
            adds.append(box([x0, PANEL_Y[1] + 0.2, BASE_Z0], [x1, PANEL_Y[1] + 2.0, BASE_TOP - WALL + 0.1]))
    # Speaker bay ribs on the inner left wall (3520 cavity speaker slides down between them)
    for yy in (-35.0 - 18.6, -35.0 + 17.0):
        adds.append(box([-BASE_W / 2 + WALL - 0.1, yy, z0], [-BASE_W / 2 + WALL + 6.0, yy + 1.6, BASE_TOP - WALL + 0.1]))
    # Hinge knuckles on the rear step, either side of the 12mm head tail (13mm gap)
    ax, ay, az = BASE_AXIS
    for x0, x1 in ((-11.5, -6.5), (6.5, 11.5)):
        adds.append(box([x0, ay - 4.5, STEP_TOP - WALL + 0.2], [x1, ay + 4.5, az]))
        adds.append(x_cylinder(4.5, x0, x1, ay, az))
    base = union([shell] + adds)

    cuts = []
    # Openings under the monitor floor (head Y -> base Y is -46): the Wio bottom-port slot,
    # the two 40-pin wire holes and a narrow slot for the hinge tail
    ty = HEAD_AXIS[1] - BASE_AXIS[1]
    cuts.append(box([-31.5, 2.5 - ty, BASE_TOP - 4.0], [31.5, 14.5 - ty, BASE_TOP + 1.0]))
    for x0, x1 in ((-32.5, -11.5), (11.5, 32.5)):
        cuts.append(box([x0, 15.5 - ty, BASE_TOP - 4.0], [x1, 24.5 - ty, BASE_TOP + 1.0]))
    cuts.append(box([-6.6, 14.0 - ty, BASE_TOP - 4.0], [6.6, STEP_Y + 0.01, BASE_TOP + 1.0]))
    # Notch in the step wall for the head tail
    cuts.append(box([-6.6, STEP_Y - WALL - 0.5, STEP_TOP + 1.0], [6.6, STEP_Y + 1.0, BASE_TOP + 1.0]))
    # Hinge bore D3.4, counterbore for the M3 bolt head on the left knuckle
    cuts.append(x_cylinder(1.7, -15.0, 15.0, ay, az, sections=32))
    # Core the knuckle blocks from below (open into the box) to keep them thin-walled
    for x0, x1 in ((-10.3, -7.7), (7.7, 10.3)):
        cuts.append(box([x0, ay - 2.5, STEP_TOP - WALL - 0.5], [x1, ay + 2.5, az - 4.3]))
    cuts.append(x_cylinder(3.1, -12.0, -9.7, ay, az, sections=32))
    if jlc:
        # Ports cut straight into the front wall, same layout as the swappable panel
        fy0, fy1 = BASE_Y0 - 1.0, BASE_Y0 + WALL + 1.0
        for _, x, z, w, h, r in FRONT_PORTS:
            cuts.append(hull(rounded_slab_y(w, h, min(r, h / 2 - 0.01), fy0, fy1, cx=x, cz=z, sections=24)))
            cuts.append(box([x - w / 2, BASE_Y0 - 0.5, z - h / 2 - 3.2], [x + w / 2, BASE_Y0 + 0.5, z - h / 2 - 2.4]))
        lx, lz, lr = FRONT_LED
        cuts.append(y_cylinder(lr, fy0, fy1, lx, lz, sections=24))
    else:
        # Pilot holes in the cover bosses
        for bx, by in BOSS_XY:
            p = trimesh.creation.cylinder(radius=1.25, height=24.0, sections=24)
            p.apply_translation([bx, by, BASE_Z0 + 12.0 - 1.0])
            cuts.append(p)
        # Front panel window
        cuts.append(box([-38.0, BASE_Y0 - 1.0, 6.0], [38.0, BASE_Y0 + WALL + 0.1, 26.0]))
    # Right side: vertical vent slots
    for i in range(10):
        y = -40.0 + i * 2.8
        cuts.append(hull(rounded_slab_x(1.6, 14.0, 0.75, BASE_W / 2 - WALL - 0.5, BASE_W / 2 + 1.0, cy=y, cz=16.0)))
    # Left side: speaker grille (6 x 4 round holes) in front of the speaker bay
    for i in range(6):
        for j in range(4):
            cuts.append(x_cylinder(1.0, -BASE_W / 2 - 1.0, -BASE_W / 2 + WALL + 0.5, -45.0 + 4.0 * i, 10.0 + 4.0 * j,
                                   sections=20))
    return cut(base, cuts)


# ==============================================================================
# Part 4: bottom cover - battery bay, module standoffs, foot pads
# ==============================================================================
def build_bottom_cover():
    D = BASE_Y1 - BASE_Y0
    cy = (BASE_Y0 + BASE_Y1) / 2
    plate = hull(rounded_slab_z(BASE_W, D, 6.0, 0.0, BASE_Z0, cy=cy))

    adds = []
    # Battery bay for a 603040 / 503040 Li-Po (40 x 30 x 6): 1.6mm walls, 7mm high
    bx0, by0, bx1, by1 = -6.0, -26.0, 35.0, 5.0
    outer = box([bx0 - 1.6, by0 - 1.6, BASE_Z0 - 0.1], [bx1 + 1.6, by1 + 1.6, BASE_Z0 + 7.0])
    inner = box([bx0, by0, BASE_Z0 - 0.5], [bx1, by1, BASE_Z0 + 8.0])
    wire = box([bx0 - 2.0, by1 - 8.0, BASE_Z0 + 2.0], [bx0 + 0.1, by1 - 2.0, BASE_Z0 + 8.0])   # lead exit
    adds.append(cut(outer, [inner, wire]))
    # Module standoffs on a 20mm grid (Grove 1x1 / 1x2 modules, M2 self-tap pilot D1.8)
    posts = [(x, y) for x in (-20.0, 0.0, 20.0) for y in (-52.0, -32.0)]
    for x, y in posts:
        c = trimesh.creation.cylinder(radius=2.5, height=5.0)
        c.apply_translation([x, y, BASE_Z0 + 2.4])
        adds.append(c)
    cover = union([plate] + adds)

    cuts = []
    for x, y in posts:
        p = trimesh.creation.cylinder(radius=0.9, height=6.0, sections=20)
        p.apply_translation([x, y, BASE_Z0 + 3.5])
        cuts.append(p)
    # Screw holes D3.4 with 90 deg countersink from below
    for bx, by in BOSS_XY:
        h = trimesh.creation.cylinder(radius=1.7, height=6.0, sections=32)
        h.apply_translation([bx, by, 1.0])
        cs = hull(trimesh.creation.cylinder(radius=3.2, height=0.5, sections=32).apply_translation([bx, by, -0.26]),
                  trimesh.creation.cylinder(radius=1.7, height=0.01, sections=32).apply_translation([bx, by, 1.2]))
        cuts.append(union([h, cs]))
    # Round foot pad recesses D10 x 0.8
    for fx, fy in [(-36.0, -44.0), (36.0, -44.0), (-36.0, -6.0), (36.0, -6.0)]:
        f = trimesh.creation.cylinder(radius=5.0, height=1.6)
        f.apply_translation([fx, fy, 0.0])
        cuts.append(f)
    return cut(cover, cuts)


# ==============================================================================
# Part 5: slide-in front panel (default port layout; reprint to customise)
# Panel coordinates: X across, Z up, Y = thickness; it sits in PANEL_Y on top of the cover.
# ==============================================================================
FRONT_PORTS = [
    # (name, x, z, w, h, r)
    ('USB-C', -30.0, 16.0, 9.4, 3.6, 1.8),
    ('Grove A', -14.0, 16.0, 11.0, 6.5, 1.0),
    ('Grove B', 0.0, 16.0, 11.0, 6.5, 1.0),
    ('Switch', 17.0, 16.0, 9.0, 4.0, 0.8),
]
FRONT_LED = (32.0, 19.0, 1.55)


def build_front_panel():
    zt = BASE_TOP - WALL - 0.2
    # 81 wide: clears the R3.8 inner corners of the box; overlaps the 76mm window by 2.5 each side
    plate = box([-40.5, PANEL_Y[0] + 0.1, BASE_Z0 + 0.1], [40.5, PANEL_Y[1] - 0.1, zt])
    cuts = []
    for _, x, z, w, h, r in FRONT_PORTS:
        cuts.append(hull(rounded_slab_y(w, h, min(r, h / 2 - 0.01), PANEL_Y[0] - 1, PANEL_Y[1] + 1, cx=x, cz=z, sections=24)))
    lx, lz, lr = FRONT_LED
    cuts.append(y_cylinder(lr, PANEL_Y[0] - 1, PANEL_Y[1] + 1, lx, lz, sections=24))
    # Engraved underline below each port (0.4mm deep, front face) - retro label strips
    for _, x, z, w, h, r in FRONT_PORTS:
        cuts.append(box([x - w / 2, PANEL_Y[0] - 0.5, z - h / 2 - 3.2], [x + w / 2, PANEL_Y[0] + 0.5, z - h / 2 - 2.4]))
    return cut(plate, cuts)


# ==============================================================================
# Part 6: hinge friction knob D12 x 8 with a captive M3 nut
# ==============================================================================
def build_tilt_tv_knob():
    body = hull(trimesh.creation.cylinder(radius=6.0, height=6.8, sections=64).apply_translation([0, 0, 3.4]),
                trimesh.creation.cylinder(radius=5.0, height=0.2, sections=64).apply_translation([0, 0, 7.9]))
    flutes = []
    for i in range(12):
        a = i * 2 * np.pi / 12
        f = trimesh.creation.cylinder(radius=0.8, height=20.0, sections=16)
        f.apply_translation([6.25 * np.cos(a), 6.25 * np.sin(a), 0.0])
        flutes.append(f)
    bore = trimesh.creation.cylinder(radius=1.7, height=20.0, sections=32)
    nut = trimesh.creation.cylinder(radius=3.35, height=5.2, sections=6)   # M3 nut 5.5 AF, 2.6 deep
    return cut(body, flutes + [bore, nut])


def head_pose(tilt_deg):
    """4x4 transform: head / rear-cover coordinates -> assembled pose, tilted back by tilt_deg."""
    T = trimesh.transformations.translation_matrix(np.subtract(BASE_AXIS, HEAD_AXIS))
    return trimesh.transformations.rotation_matrix(np.radians(-tilt_deg), [1, 0, 0], BASE_AXIS) @ T


def knob_pose():
    """Knob (nut face at Z=0) on the right knuckle face, 0.2mm off."""
    R = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])          # +Z -> +X
    return trimesh.transformations.translation_matrix([11.7, BASE_AXIS[1], BASE_AXIS[2]]) @ R


def export_stl(mesh, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mesh.export(path)
    loaded = trimesh.load(path)
    vol_cm3 = loaded.volume / 1000.0
    weight = vol_cm3 * 1.15
    dims = loaded.extents
    print(f"Exported: {path:42s} | Vol: {vol_cm3:5.2f}cm³ | Size: {dims[0]:.1f}x{dims[1]:.1f}x{dims[2]:.1f}mm | {weight:4.1f}g")


def build_jlc_monitor():
    """JLC free-print monitor: front shell + CRT rear cover fused into one part. The Wio drops in
    from the top; two rails behind it keep it against the front wall."""
    head = build_tilt_tv_head(top_load=True)
    cover = build_rear_cover(fused=True)
    rails = [box([-36.6, 14.5, 3.0], [-33.5, 16.5, 61.0]), box([33.5, 14.5, 3.0], [36.6, 16.5, 61.0])]
    return union([head, cover] + rails)


JLC_PARTS = {
    '01_jlc_monitor': build_jlc_monitor,
    '02_jlc_base': lambda: build_tilt_tv_base(jlc=True),
}

PARTS = {
    'head': build_tilt_tv_head,
    'rear_cover': build_rear_cover,
    'base': build_tilt_tv_base,
    'bottom_cover': build_bottom_cover,
    'front_panel': build_front_panel,
    'knob': build_tilt_tv_knob,
}


def main():
    print("=" * 75)
    print("Building Wio retro desktop monitor parts...")
    print("=" * 75)
    for name, build in PARTS.items():
        export_stl(build(), f'cad/stl/wio_tilt_tv_{name}.stl')
    print("\nJLC free-print set (2 parts, <= 70 cm3 per order):")
    for name, build in JLC_PARTS.items():
        export_stl(build(), f'cad/stl/jlc_free/{name}.stl')
    print("\nAll parts exported.")


if __name__ == '__main__':
    main()
