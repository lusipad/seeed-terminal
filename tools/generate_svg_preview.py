"""
generate_svg_preview.py - Renders cad/tilt_tv_product_preview.svg straight from the STL meshes.

Nothing in the drawing is hand-typed geometry:
  * every outline is a projected mesh edge (sharp edges + view silhouettes),
    split into visible / hidden runs with a z-buffer (hidden-line removal);
  * every dimension value is measured on the mesh (bounding boxes, plane
    sections, ray probes) and printed to stdout for cross-checking;
  * the assembly pose uses the pivot axes measured on head and base.

Usage (from repo root):  python tools/generate_svg_preview.py
"""

import math
import os
from functools import reduce

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

STL_DIR = 'cad/stl'
OUT = 'cad/tilt_tv_product_preview.svg'

ZBUF_RES = 0.08        # mm per z-buffer pixel
SHARP_DEG = 20.0       # dihedral angle above which an edge is drawn (cylinder facets are 11.25 deg)
DENSITY = 1.15         # g/cm3, 9600 resin

# ------------------------------------------------------------------------------
# Views: (right, up, toward-viewer); right x up == toward-viewer
# ------------------------------------------------------------------------------
VIEWS = {
    'front':  ((1, 0, 0), (0, 0, 1), (0, -1, 0)),   # looking at the screen (+Y)
    'rear':   ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    'right':  ((0, 1, 0), (0, 0, 1), (1, 0, 0)),    # from +X, front of TV on the left
    'left':   ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
    'top':    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),    # front of TV at the bottom
    'bottom': ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
}


def iso_view(az_deg, el_deg):
    """Camera on a sphere: az measured from -Y (front) toward +X, el above horizon."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    w = np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
    u = np.cross([0, 0, 1], w)
    u /= np.linalg.norm(u)
    v = np.cross(w, u)
    return tuple(u), tuple(v), tuple(w)


# ------------------------------------------------------------------------------
# Projection / hidden-line engine
# ------------------------------------------------------------------------------
class Projection:
    """Orthographic projection of one or more meshes with a z-buffer."""

    def __init__(self, meshes, view, res=ZBUF_RES, bounds=None):
        self.meshes = meshes
        self.res = res
        self.R = np.array(view, dtype=float)          # rows: u, v, w
        self.w = self.R[2]
        if bounds is None:
            pts = np.vstack([m.vertices @ self.R.T for m in meshes])
            bounds = (pts[:, :2].min(0) - 1.0, pts[:, :2].max(0) + 1.0)
        self.lo, self.hi = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
        n = np.ceil((self.hi - self.lo) / res).astype(int) + 1
        self.zbuf = np.full((n[1], n[0]), -np.inf)
        self.fbuf = np.full((n[1], n[0]), -1, dtype=np.int64)   # (mesh_idx << 32) | face
        for mi, m in enumerate(meshes):
            self._raster(m, mi)

    def _raster(self, mesh, mi):
        P = mesh.vertices @ self.R.T
        tri = P[mesh.faces]
        for fi, t in enumerate(tri):
            px = (t[:, :2] - self.lo) / self.res
            x0, y0 = np.maximum(np.floor(px.min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(px.max(0)).astype(int), np.array(self.zbuf.shape[::-1]) - 1)
            if x0 > x1 or y0 > y1:
                continue
            (ax, ay), (bx, by), (cx, cy) = px
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            if not inside.any():
                continue
            d = l1 * t[0, 2] + l2 * t[1, 2] + l3 * t[2, 2]
            sub = self.zbuf[y0:y1 + 1, x0:x1 + 1]
            fsub = self.fbuf[y0:y1 + 1, x0:x1 + 1]
            upd = inside & (d > sub)
            sub[upd] = d[upd]
            fsub[upd] = (mi << 32) | fi

    def _visible(self, p2, d):
        ix = ((p2[:, 0] - self.lo[0]) / self.res).astype(int)
        iy = ((p2[:, 1] - self.lo[1]) / self.res).astype(int)
        h, w = self.zbuf.shape
        best = np.full(len(d), np.inf)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy = np.clip(iy + dy, 0, h - 1)
                xx = np.clip(ix + dx, 0, w - 1)
                best = np.minimum(best, self.zbuf[yy, xx])
        return d >= best - 0.06

    def edges(self, mi):
        """Return (visible, hidden) lists of 2D polylines for mesh mi."""
        m = self.meshes[mi]
        n = m.face_normals @ self.w
        fa = m.face_adjacency
        sharp = m.face_adjacency_angles > math.radians(SHARP_DEG)
        front = n > 1e-6
        silhouette = front[fa[:, 0]] != front[fa[:, 1]]
        sel = sharp | silhouette
        P = m.vertices @ self.R.T
        vis, hid = [], []
        for a, b in m.face_adjacency_edges[sel]:
            pa, pb = P[a], P[b]
            L = np.linalg.norm(pb[:2] - pa[:2])
            if L < 0.02:
                continue
            k = max(2, int(L / 0.12) + 1)
            t = np.linspace(0, 1, k)
            s = pa[None] * (1 - t[:, None]) + pb[None] * t[:, None]
            flag = self._visible(s[:, :2], s[:, 2])
            if k >= 3:  # drop single-sample flicker
                f = flag.astype(int)
                f[1:-1] = (f[:-2] + f[1:-1] + f[2:]) >= 2
                flag = f.astype(bool)
            start = 0
            for i in range(1, k + 1):
                if i == k or flag[i] != flag[start]:
                    seg = (s[start, :2], s[min(i, k - 1), :2] if i < k else s[k - 1, :2])
                    if i < k:
                        seg = (s[start, :2], s[i, :2])
                    (vis if flag[start] else hid).append(seg)
                    start = i
        return vis, hid

    def silhouette(self, mi):
        m = self.meshes[mi]
        P = (m.vertices @ self.R.T)[:, :2]
        polys = [Polygon(P[f]) for f in m.faces]
        polys = [p for p in polys if p.area > 1e-6]
        return unary_union(polys).buffer(0.01).buffer(-0.01)

    def shaded(self, light=(-0.35, -0.55, 0.75)):
        """Visible triangles (per z-buffer ownership), far-to-near, with a Lambert factor."""
        owned = np.unique(self.fbuf[self.fbuf >= 0])
        L = np.array(light, float)
        L /= np.linalg.norm(L)
        out = []
        for key in owned:
            mi, fi = int(key >> 32), int(key & 0xffffffff)
            m = self.meshes[mi]
            P = m.vertices[m.faces[fi]] @ self.R.T
            nrm = m.face_normals[fi]
            lam = 0.42 + 0.58 * max(0.0, float(nrm @ L))
            out.append((P[:, 2].mean(), mi, P[:, :2], lam))
        out.sort(key=lambda r: r[0])
        return out


# ------------------------------------------------------------------------------
# Measurement helpers (all dimensions come from here)
# ------------------------------------------------------------------------------
def section(mesh, origin, normal, u, v):
    """Planar cross-section as a shapely geometry in (u, v) coordinates (even-odd fill)."""
    segs = trimesh.intersections.mesh_plane(mesh, normal, origin)
    u, v = np.array(u, float), np.array(v, float)
    lines = [((float(a @ u), float(a @ v)), (float(b @ u), float(b @ v))) for a, b in segs]
    lines = [tuple((round(x, 5), round(y, 5)) for x, y in l) for l in lines]
    faces = [Polygon(f.exterior) for f in polygonize(lines)]
    if not faces:
        return Polygon()
    return reduce(lambda g, f: g.symmetric_difference(f), faces)


def holes(geom):
    """Interior rings (holes) of a section, as shapely Polygons sorted by area desc."""
    geoms = getattr(geom, 'geoms', [geom])
    hs = [Polygon(r) for g in geoms for r in g.interiors]
    return sorted(hs, key=lambda p: -p.area)


def parts(geom):
    return sorted(getattr(geom, 'geoms', [geom]), key=lambda p: -p.area)


def ray_hits(mesh, origin, direction):
    loc, _, _ = mesh.ray.intersects_location([origin], [direction])
    d = np.array(direction, float)
    t = sorted(float((p - origin) @ d) for p in loc)
    out = []
    for x in t:  # merge duplicates from shared triangle edges
        if not out or abs(x - out[-1]) > 1e-4:
            out.append(x)
    return out


def bbox2(p):
    x0, y0, x1, y1 = p.bounds
    return x0, y0, x1, y1, x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2


def measure(head, base, knob):
    M = {}
    for name, m in (('head', head), ('base', base), ('knob', knob)):
        M[name] = dict(lo=m.bounds[0], hi=m.bounds[1], ext=m.extents,
                       vol=m.volume / 1000.0, area=m.area / 100.0,
                       shells=len(m.split(only_watertight=False)), watertight=m.is_watertight,
                       faces=len(m.faces))
    H = M['head']
    hz0 = H['lo'][2]

    # Head: front silhouette holes = see-through openings (screen window, joystick)
    front = Projection([head], VIEWS['front']).silhouette(0)
    hs = holes(front)
    H['screen'] = bbox2(hs[0])
    H['joy'] = bbox2(hs[1])
    # Front bezel lip: probe just behind the front face
    xs = ray_hits(head, np.array([-200.0, 1.5, 32.0]), [1, 0, 0])
    H['bez_x'] = (xs[0] - 200.0, xs[-1] - 200.0)
    zs = ray_hits(head, np.array([-20.0, 1.5, -50.0]), [0, 0, 1])
    H['bez_z'] = (zs[0] - 50.0, zs[-1] - 50.0)
    # Cabinet body behind the bezel: probe at mid depth
    xs = ray_hits(head, np.array([-200.0, 13.0, 56.0]), [1, 0, 0])
    H['cab_x'] = (xs[0] - 200.0, xs[-1] - 200.0)
    H['side_wall'] = xs[1] - xs[0]
    ys = ray_hits(head, np.array([0.0, -50.0, 56.0]), [0, 1, 0])
    H['cab_y'] = (ys[0] - 50.0, None)
    H['front_wall'] = ys[1] - ys[0]
    zs = ray_hits(head, np.array([-20.0, 22.0, -50.0]), [0, 0, 1])
    H['cab_z'] = (zs[0] - 50.0, zs[-1] - 50.0)
    H['bottom_wall'] = zs[1] - zs[0]
    H['top_wall'] = zs[-1] - zs[-2]
    # Rear opening (slide-in pocket): section just inside the back face
    rear_y = H['hi'][1] - 0.3
    rear = section(head, [0, rear_y, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1))
    H['pocket'] = bbox2(holes(rear)[0])
    H['cab_y'] = (H['cab_y'][0], H['hi'][1])
    # Pocket front stop (Wio rests against the inside of the front wall)
    ys2 = ray_hits(head, np.array([0.0, 200.0, 56.0]), [0, -1, 0])
    H['pocket_front_y'] = 200.0 - ys2[0]
    H['pocket_depth'] = H['hi'][1] - H['pocket_front_y']
    # Dials: section through the bosses in front of the face
    dials = parts(section(head, [0, -0.5, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1)))
    H['dials'] = sorted([bbox2(d) for d in dials], key=lambda b: -b[7])
    H['dial_proud'] = -H['lo'][1]
    # Top button slot: ray probes through the roof along x=0
    zr = H['cab_z'][1] - 1.0
    ys3 = ray_hits(head, np.array([0.0, -50.0, zr]), [0, 1, 0])
    xs3 = ray_hits(head, np.array([-200.0, (ys3[1] + ys3[2]) / 2 - 50.0, zr]), [1, 0, 0])
    sy0, sy1 = ys3[1] - 50.0, ys3[2] - 50.0
    sx0, sx1 = xs3[1] - 200.0, xs3[2] - 200.0
    H['btn_slot'] = (sx0, sy0, sx1, sy1, sx1 - sx0, sy1 - sy0, (sx0 + sx1) / 2, (sy0 + sy1) / 2)
    # Antenna: ball tips from a slice through the ball equators (top - ball radius)
    ball_r = None
    for dz in np.arange(0.6, 4.0, 0.1):          # widest slice = ball equator
        sl = parts(section(head, [0, 0, H['hi'][2] - dz], [0, 0, 1], (1, 0, 0), (0, 1, 0)))
        if len(sl) == 2 and (ball_r is None or bbox2(sl[0])[4] / 2 > ball_r + 1e-3):
            ball_r = bbox2(sl[0])[4] / 2
            tips = sl
    H['ant'] = sorted([bbox2(e) for e in tips], key=lambda b: b[6])
    H['ant_ball_d'] = 2 * ball_r
    H['ant_top'] = H['hi'][2]
    H['ant_span'] = H['ant'][1][6] - H['ant'][0][6]
    # Web between the screen window and the joystick hole (thinnest front-face bridge)
    H['web'] = H['joy'][0] - H['screen'][2]
    # Type-C: section through the left wall
    lw = H['cab_x'][0] + H['side_wall'] / 2
    tc = section(head, [lw, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    H['typec'] = bbox2(holes(tc)[0]) if holes(tc) else bbox2(
        sorted(parts(tc), key=lambda p: p.bounds[1])[0])
    # Pivot lug: section on the centre plane x=0 below the cabinet
    lug = section(head, [0, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    lug_h = [bbox2(h) for h in holes(lug) if h.bounds[3] < H['cab_z'][0] + 0.01]
    piv = min(lug_h, key=lambda b: b[4])
    H['pivot'] = (0.0, piv[6], piv[7])
    H['pivot_d'] = piv[4]
    xs = ray_hits(head, np.array([-200.0, piv[6], hz0 + 0.8]), [1, 0, 0])
    H['lug_w'] = xs[-1] - xs[0]
    yz = section(head, [0, 0, hz0 + 0.8], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    H['lug_r'] = H['pivot'][2] - hz0

    B = M['base']
    ys = ray_hits(base, np.array([0.0, -200.0, 1.0]), [0, 1, 0])
    xs_plate = ray_hits(base, np.array([-200.0, 30.0, 3.5]), [1, 0, 0])
    B['plate_x'] = (xs_plate[0] - 200.0, xs_plate[-1] - 200.0)
    zs = ray_hits(base, np.array([-25.0, 25.0, 50.0]), [0, 0, -1])
    B['plate_top'] = 50.0 - zs[0]
    B['deck'] = zs[1] - zs[0]
    zr = ray_hits(base, np.array([0.0, 25.0, 50.0]), [0, 0, -1])
    B['rib_full'] = zr[-1] - zr[0]
    # Arms: probe across X at mid arm height
    zm = (B['plate_top'] + B['hi'][2]) / 2 - 3
    xa = ray_hits(base, np.array([-200.0, 0.0, zm]), [1, 0, 0])
    xa = [x - 200.0 for x in xa]
    B['arm_l'] = (xa[0], xa[1])
    B['arm_r'] = (xa[-2], xa[-1])
    B['gap'] = xa[2] - xa[1] if len(xa) == 4 else None
    ya = ray_hits(base, np.array([-8.35, -200.0, zm]), [0, 1, 0])
    B['arm_y'] = (ya[0] - 200.0, ya[-1] - 200.0)
    # Pivot hole: section through the right arm
    rs = section(base, [(B['arm_r'][0] + B['arm_r'][1]) / 2, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    ph = bbox2(holes(rs)[0])
    B['pivot'] = (0.0, ph[6], ph[7])
    B['pivot_d'] = ph[4]
    B['arm_r_round'] = B['hi'][2] - ph[7]
    # Nut trap / counterbore: sections in the outer skins
    nl = section(base, [B['arm_l'][0] + 0.3, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    B['hex'] = bbox2(holes(nl)[0])
    B['hex_depth'] = ray_hits(base, np.array([-200.0, ph[6] + 2.4, ph[7]]), [1, 0, 0])[0] - 200.0 - B['arm_l'][0]
    cr = section(base, [B['arm_r'][1] - 0.3, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    B['cbore_d'] = bbox2(holes(cr)[0])[4]
    cb = ray_hits(base, np.array([200.0, ph[6] + 2.5, ph[7]]), [-1, 0, 0])
    B['cbore_depth'] = B['arm_r'][1] - (200.0 - cb[0])
    # Underside: pocket, ribs, foot recesses
    und = section(base, [0, 0, 0.5], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    hs = holes(und)
    B['feet'] = sorted([bbox2(h) for h in hs if h.area < 100], key=lambda b: (b[7], b[6]))
    B['pockets'] = [bbox2(h) for h in hs if h.area >= 100]
    pk = unary_union([h for h in hs if h.area >= 100])
    B['pocket_env'] = bbox2(pk.envelope)
    pxs = sorted(B['pockets'], key=lambda b: b[0])
    B['rib_w'] = pxs[-1][0] - pxs[0][2]
    # Foot pads: only count recesses that actually exist in the mesh (they may fall inside the pocket)
    B['foot_depth'] = None
    if B['feet']:
        fz = ray_hits(base, np.array([B['feet'][0][6], B['feet'][0][7], -10.0]), [0, 0, 1])
        B['foot_depth'] = fz[0] - 10.0
    # Contact area with the desk (z = 0 face)
    B['contact'] = und.area

    K = M['knob']
    ks = section(knob, [0, 0, 0.3], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    K['hex'] = bbox2(holes(ks)[0])
    km = section(knob, [0, 0, 5.0], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    K['bore'] = bbox2(holes(km)[0])[4]
    kz = ray_hits(knob, np.array([0.0, 6.0, 50.0]), [0, 0, -1])
    K['collar_h'] = K['hi'][2] - (50.0 - kz[0]) if kz else None
    K['body_h'] = 50.0 - kz[0]
    kc = section(knob, [0, 0, K['hi'][2] - 0.3], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    K['collar_d'] = bbox2(parts(kc)[0])[4]
    K['ridges'] = 12
    hd = ray_hits(knob, np.array([0.0, 2.6, -10.0]), [0, 0, 1])
    K['hex_depth'] = hd[0] - 10.0
    return M


def head_pose(M, tilt_deg):
    """4x4 transform taking head coordinates to the assembled pose (pivot on pivot, tilted back)."""
    hp, bp = np.array(M['head']['pivot']), np.array(M['base']['pivot'])
    return trimesh.transformations.rotation_matrix(math.radians(-tilt_deg), [1, 0, 0], bp) @         trimesh.transformations.translation_matrix(bp - hp)


def assemble(head, base, knob, M, tilt_deg):
    """Head pivot onto base pivot, tilted back by tilt_deg; knob on the -X arm face."""
    bp = np.array(M['base']['pivot'])
    h = head.copy()
    h.apply_transform(head_pose(M, tilt_deg))
    k = knob.copy()
    k.apply_transform(trimesh.transformations.rotation_matrix(math.radians(-90), [0, 1, 0]))  # +Z -> -X
    k.apply_translation([M['base']['arm_l'][0], bp[1], bp[2]])
    return h, base.copy(), k


# ------------------------------------------------------------------------------
# SVG helpers
# ------------------------------------------------------------------------------
INK = '#e2e8f0'
HID = '#64748b'
DIM = '#38bdf8'
CEN = '#f87171'
ACC = '#f59e0b'
OK = '#34d399'
BAD = '#f43f5e'
FILL = {'head': '#1e293b', 'base': '#172235', 'knob': '#3b2a12'}
SHADE = {'head': (236, 230, 216), 'base': (88, 96, 110), 'knob': (200, 150, 80)}


def f1(x):
    return f'{x:.1f}'


class Canvas:
    def __init__(self):
        self.out = []

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=11, fill=INK, anchor='start', weight='normal', cls=None, rot=None):
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ''
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}" font-weight="{weight}"{tr}>{s}</text>')


class ViewFrame:
    """Places a Projection on the canvas: mm (u, v) -> px with a given origin and scale."""

    def __init__(self, cv, proj, ox, oy, scale):
        self.cv, self.p, self.ox, self.oy, self.s = cv, proj, ox, oy, scale

    def xy(self, u, v):
        return self.ox + u * self.s, self.oy - v * self.s

    def pt3(self, p):
        q = np.asarray(p, float) @ self.p.R.T
        return q[0], q[1]

    def path(self, segs):
        d = []
        for a, b in segs:
            x0, y0 = self.xy(*a)
            x1, y1 = self.xy(*b)
            d.append(f'M{x0:.1f} {y0:.1f}L{x1:.1f} {y1:.1f}')
        return ''.join(d)

    def poly_path(self, geom):
        d = []
        for g in getattr(geom, 'geoms', [geom]):
            if g.is_empty:
                continue
            for ring in [g.exterior] + list(g.interiors):
                c = list(ring.coords)
                d.append('M' + 'L'.join(f'{self.xy(*p)[0]:.1f} {self.xy(*p)[1]:.1f}' for p in c) + 'Z')
        return ''.join(d)

    def draw(self, kinds, fill=True, hidden=True, width=1.3):
        for mi, kind in enumerate(kinds):
            if fill:
                self.cv.add(f'<path d="{self.poly_path(self.p.silhouette(mi))}" fill="{FILL[kind]}" '
                            f'fill-rule="evenodd" stroke="none"/>')
        for mi, kind in enumerate(kinds):
            vis, hid = self.p.edges(mi)
            if hidden and hid:
                self.cv.add(f'<path d="{self.path(hid)}" stroke="{HID}" stroke-width="0.7" '
                            f'stroke-dasharray="3 2" fill="none"/>')
            self.cv.add(f'<path d="{self.path(vis)}" stroke="{INK}" stroke-width="{width}" '
                        f'stroke-linecap="round" fill="none"/>')

    def draw_shaded(self, kinds, edge_w=0.9):
        self.cv.add('<g stroke-width="0.35" stroke-linejoin="round">')
        for _, mi, P, lam in self.p.shaded():
            r, g, b = (int(c * lam) for c in SHADE[kinds[mi]])
            pts = ' '.join(f'{self.xy(*q)[0]:.1f},{self.xy(*q)[1]:.1f}' for q in P)
            col = f'#{r:02x}{g:02x}{b:02x}'
            self.cv.add(f'<polygon points="{pts}" fill="{col}" stroke="{col}"/>')
        self.cv.add('</g>')
        for mi in range(len(kinds)):
            vis, _ = self.p.edges(mi)
            self.cv.add(f'<path d="{self.path(vis)}" stroke="#0b1220" stroke-opacity="0.55" '
                        f'stroke-width="{edge_w}" fill="none"/>')

    # --- annotation primitives (all inputs in mm, view coordinates) ---
    def hdim(self, u0, u1, v, v_ref0=None, v_ref1=None, label=None, below=False):
        x0, y = self.xy(u0, v)
        x1, _ = self.xy(u1, v)
        for u, vr in ((u0, v_ref0), (u1, v_ref1)):
            if vr is not None:
                xe, ye = self.xy(u, vr)
                self.cv.add(f'<line x1="{xe:.1f}" y1="{ye:.1f}" x2="{xe:.1f}" y2="{y + (4 if ye < y else -4):.1f}" '
                            f'stroke="{DIM}" stroke-width="0.5" stroke-dasharray="2 2"/>')
        self.cv.add(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" stroke="{DIM}" '
                    f'stroke-width="0.9" marker-start="url(#ar)" marker-end="url(#ar)"/>')
        ty = y + 13 if below else y - 4
        self.cv.text((x0 + x1) / 2, ty, label or f1(abs(u1 - u0)), 10.5, DIM, 'middle', 'bold')

    def vdim(self, v0, v1, u, u_ref0=None, u_ref1=None, label=None, left=True):
        x, y0 = self.xy(u, v0)
        _, y1 = self.xy(u, v1)
        for v, ur in ((v0, u_ref0), (v1, u_ref1)):
            if ur is not None:
                xe, ye = self.xy(ur, v)
                self.cv.add(f'<line x1="{xe:.1f}" y1="{ye:.1f}" x2="{x + (4 if xe > x else -4):.1f}" y2="{ye:.1f}" '
                            f'stroke="{DIM}" stroke-width="0.5" stroke-dasharray="2 2"/>')
        self.cv.add(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" stroke="{DIM}" '
                    f'stroke-width="0.9" marker-start="url(#ar)" marker-end="url(#ar)"/>')
        tx = x - 5 if left else x + 13
        self.cv.text(tx, (y0 + y1) / 2, label or f1(abs(v1 - v0)), 10.5, DIM, 'middle', 'bold', rot=-90)

    def center(self, u, v, r):
        x, y = self.xy(u, v)
        rr = r * self.s
        self.cv.add(f'<path d="M{x - rr:.1f} {y:.1f}H{x + rr:.1f}M{x:.1f} {y - rr:.1f}V{y + rr:.1f}" '
                    f'stroke="{CEN}" stroke-width="0.6" stroke-dasharray="8 2 2 2"/>')

    def cline(self, u0, v0, u1, v1):
        x0, y0 = self.xy(u0, v0)
        x1, y1 = self.xy(u1, v1)
        self.cv.add(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{CEN}" '
                    f'stroke-width="0.6" stroke-dasharray="10 2 2 2"/>')

    def note(self, u, v, tx, ty, s, color=ACC, anchor='start'):
        x, y = self.xy(u, v)
        self.cv.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="{color}"/>')
        self.cv.add(f'<polyline points="{x:.1f},{y:.1f} {tx:.1f},{ty:.1f} '
                    f'{tx + (40 if anchor == "start" else -40):.1f},{ty:.1f}" fill="none" '
                    f'stroke="{color}" stroke-width="0.7"/>')
        self.cv.text(tx + (3 if anchor == 'start' else -3), ty - 3, s, 10, color, anchor)


def panel(cv, x, y, w, h, tag, title, sub):
    cv.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#0d1526" stroke="#1f2a3e"/>')
    cv.text(x + 14, y + 24, f'{tag}  {title}', 14, '#7dd3fc', weight='bold')
    cv.text(x + 14, y + 41, sub, 10.5, '#64748b')


def view_label(cv, x, y, s):
    cv.text(x, y, s, 10.5, '#94a3b8', 'middle', 'bold')


# ------------------------------------------------------------------------------
# Drawing
# ------------------------------------------------------------------------------
def build():
    head = trimesh.load(f'{STL_DIR}/wio_tilt_tv_head.stl')
    base = trimesh.load(f'{STL_DIR}/wio_tilt_tv_base.stl')
    knob = trimesh.load(f'{STL_DIR}/wio_tilt_tv_knob.stl')
    M = measure(head, base, knob)
    H, B, K = M['head'], M['base'], M['knob']

    # Assembly checks
    tilt_samples = [0, 15, 30, 45]
    clash = {}
    for t in tilt_samples:
        h, b, _ = assemble(head, base, knob, M, t)
        inter = trimesh.boolean.intersection([h, b], engine='manifold')
        clash[t] = (inter.volume if len(inter.faces) else 0.0, inter)
    bp = np.array(B['pivot'])
    pivot_to_cab = H['pivot'][2] - H['cab_z'][0] if False else H['cab_z'][0] - H['pivot'][2]
    clash_mm = B['arm_r_round'] - pivot_to_cab

    W, HH = 1800, 1320
    cv = Canvas()
    cv.add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HH}" width="{W}" height="{HH}" '
           f'font-family="Consolas, \'Microsoft YaHei\', \'PingFang SC\', monospace">')
    cv.add('<defs><marker id="ar" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 1.5L10 5L0 8.5z" fill="#38bdf8"/></marker>'
           '<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse">'
           '<path d="M20 0H0V20" fill="none" stroke="#111a2b" stroke-width="0.6"/></pattern></defs>')
    cv.add(f'<rect width="{W}" height="{HH}" fill="#0a0f1d"/><rect width="{W}" height="{HH}" fill="url(#g)"/>')

    # Title block
    cv.text(28, 40, 'WIO TERMINAL 可俯仰复古小电视 — STL 实测三视图 / 装配图', 22, '#f8fafc', weight='bold')
    cv.text(28, 62, f'DWG WT-TILT-TV REV4  |  单位 mm  |  各视图观察方向见图名  |  所有轮廓 = STL 网格边投影 + z-buffer 消隐'
                    f'（实线可见 / 虚线隐藏）  |  所有尺寸 = 网格截面/射线实测', 11.5, '#94a3b8')
    cv.text(28, 80, 'source: cad/stl/wio_tilt_tv_head.stl · wio_tilt_tv_base.stl · wio_tilt_tv_knob.stl  '
                    '— regenerate: python tools/generate_svg_preview.py', 11, '#475569')

    # ==========================================================================
    # [A] HEAD  (front / right / top / rear)  scale 2.6
    # ==========================================================================
    S = 2.6
    panel(cv, 20, 96, 1060, 640, '[A]', f'机头 wio_tilt_tv_head.stl',
          f'外形 {f1(H["ext"][0])} × {f1(H["ext"][1])} × {f1(H["ext"][2])}  |  体积 {H["vol"]:.2f} cm³  |  '
          f'≈{H["vol"] * DENSITY:.1f} g  |  比例 {S}:1 px/mm')

    # Front view
    pf = Projection([head], VIEWS['front'])
    vf = ViewFrame(cv, pf, 190, 0, S)
    vf.ox = 70 + (-H['lo'][0]) * S + 40
    vf.oy = 210 + H['hi'][2] * S
    vf.draw(['head'])
    sw = H['screen']
    vf.center(sw[6], sw[7], sw[4] / 2 + 3)
    jy = H['joy']
    vf.center(jy[6], jy[7], jy[4] / 2 + 3)
    for d in H['dials']:
        vf.center(d[6], d[7], d[4] / 2 + 2)
    cx0, cx1 = H['bez_x']
    cz0, cz1 = H['bez_z']
    vf.hdim(cx0, cx1, H['lo'][2] - 9, cz0, cz0, label=f'{f1(cx1 - cx0)}', below=True)
    vf.hdim(sw[0], sw[2], sw[3] + 4, sw[3], sw[3], label=f'窗 {f1(sw[4])}')
    vf.vdim(sw[1], sw[3], sw[0] - 4, sw[0], sw[0], label=f1(sw[5]), left=True)
    vf.vdim(cz0, cz1, cx0 - 9, cx0, cx0, label=f1(cz1 - cz0))
    vf.vdim(H['lo'][2], H['hi'][2], cx0 - 21, 0, H['ant'][0][6], label=f'总高 {f1(H["ext"][2])}')
    vf.vdim(cz0, sw[1], sw[0] + 6, None, None, label=f1(sw[1] - cz0), left=False)
    e0, e1 = H['ant']
    vf.hdim(e0[6], e1[6], H['hi'][2] + 6, H['hi'][2], H['hi'][2], label=f'天线展开 {f1(H["ant_span"])}')
    vf.hdim(-H['lug_w'] / 2, H['lug_w'] / 2, H['lo'][2] - 3, None, None, label=f'凸耳 {f1(H["lug_w"])}', below=True)
    vf.note(jy[6] + jy[4] / 2 * 0.7, jy[7] - jy[4] / 2 * 0.7, vf.xy(cx1, 0)[0] + 18, vf.xy(0, jy[7] - 9)[1],
            f'摇杆孔 Ø{f1(jy[4])}')
    d0 = H['dials'][0]
    vf.note(d0[6] + d0[4] / 2 * 0.7, d0[7] + d0[4] / 2 * 0.7, vf.xy(cx1, 0)[0] + 18, vf.xy(0, d0[7] + 9)[1],
            f'旋钮凸台 Ø{f1(d0[4])} ×2')
    vf.note(sw[6], sw[7], vf.xy(sw[6], 0)[0] - 30, vf.xy(0, sw[7] + 4)[1], '通透（后部开口）', HID)
    view_label(cv, vf.xy(0, 0)[0], vf.xy(0, H['lo'][2])[1] + 56, '主视图 FRONT')

    # Right view (to the right of the front view in 1st-angle = viewed from left; we label explicitly)
    pr = Projection([head], VIEWS['right'])
    vr = ViewFrame(cv, pr, 0, vf.oy, S)
    vr.ox = 470 - H['lo'][1] * S
    vr.draw(['head'])
    py, pz = H['pivot'][1], H['pivot'][2]
    vr.center(py, pz, H['lug_r'] + 3)
    vr.hdim(H['lo'][1], H['hi'][1], H['lo'][2] - 9, cz0, cz0, label=f'{f1(H["ext"][1])}', below=True)
    vr.vdim(H['lo'][2], cz0, H['hi'][1] + 8, None, None, label=f1(cz0 - H['lo'][2]), left=False)
    vr.vdim(pz, cz0, H['hi'][1] + 20, py, None, label=f1(cz0 - pz), left=False)
    vr.note(py + 1.3, pz - 1.3, vr.xy(H['hi'][1], 0)[0] + 34, vr.xy(0, pz - 9)[1],
            f'转轴孔 Ø{f1(H["pivot_d"])} / R{f1(H["lug_r"])}')
    vr.note(H['pocket_front_y'], 40, vr.xy(H['hi'][1], 0)[0] + 34, vr.xy(0, 44)[1],
            f'前挡壁 {f1(H["front_wall"])}（虚线=内腔）', HID)
    view_label(cv, vr.xy(13, 0)[0], vr.xy(0, H['lo'][2])[1] + 56, '右视图 RIGHT (+X)')

    # Rear view
    pb = Projection([head], VIEWS['rear'])
    vb = ViewFrame(cv, pb, 0, vf.oy, S)
    vb.ox = 830 + H['hi'][0] * S * 0
    vb.draw(['head'])
    pk = H['pocket']
    # rear view u = -x
    vb.hdim(-pk[2], -pk[0], pk[3] - 6, None, None, label=f'插口 {f1(pk[4])}')
    vb.vdim(pk[1], pk[3], -pk[2] - 4, -pk[2], -pk[2], label=f1(pk[5]))
    vb.vdim(cz0, pk[1], -pk[0] + 6, None, None, label=f1(pk[1] - cz0), left=False)
    vb.hdim(-cx1, -pk[2], pk[1] - 5, None, None, label=f1(H['side_wall']), below=True)
    tcx = H['typec']
    vb.note(-H['cab_x'][0], tcx[7], vb.xy(-H['cab_x'][0], 0)[0] + 22, vb.xy(0, tcx[7] + 13)[1],
            f'Type-C {f1(tcx[4])}×{f1(tcx[5])}')
    view_label(cv, vb.xy(0, 0)[0], vb.xy(0, H['lo'][2])[1] + 56, '后视图 REAR（Wio 从后插入）')

    # Top view under the front view
    pt = Projection([head], VIEWS['top'])
    vt = ViewFrame(cv, pt, vf.ox, 0, S)
    vt.oy = 545 + H['hi'][1] * S
    vt.draw(['head'])
    bs = H['btn_slot']
    vt.hdim(bs[0], bs[2], H['lo'][1] - 5, bs[1], bs[1], label=f'按键槽 {f1(bs[4])}', below=True)
    vt.vdim(bs[1], bs[3], bs[2] + 4, bs[2], bs[2], label=f1(bs[5]), left=False)
    vt.vdim(0, H['hi'][1], cx1 + 8, cx1, cx1, label=f1(H['hi'][1]), left=False)
    for e in H['ant']:
        vt.center(e[6], e[7], e[4] / 2 + 2)
    vt.note(H['ant'][1][6] + 1.5, H['ant'][1][7] + 1.5, vt.xy(cx1, 0)[0] + 72, vt.xy(0, 10)[1],
            f'天线球头 Ø{f1(H["ant_ball_d"])} → 顶 Z{f1(H["ant_top"])}')
    vt.vdim(H['lo'][1], 0, cx0 - 6, None, cx0, label=f1(-H['lo'][1]))
    view_label(cv, vt.xy(0, 0)[0], vt.xy(0, H['lo'][1])[1] + 48, '俯视图 TOP')

    # Head feature table
    tx, ty = 560, 560
    rows = [
        ('前框 / 机身', f'{f1(cx1 - cx0)} × {f1(cz1 - cz0)} / {f1(H["cab_x"][1] - H["cab_x"][0])} × '
                      f'{f1(H["cab_z"][1] - H["cab_z"][0])}，深 {f1(H["hi"][1])}'),
        ('屏幕视窗', f'{f1(sw[4])} × {f1(sw[5])}，中心 X{sw[6]:+.1f} Z{f1(sw[7])}'),
        ('后插口 (Wio 72×57)', f'{f1(pk[4])} × {f1(pk[5])}，深 {f1(H["hi"][1] - H["pocket_front_y"])}'),
        ('壁厚 前/侧/顶/底', f'{f1(H["front_wall"])} / {f1(H["side_wall"])} / {f1(H["top_wall"])} / {f1(H["bottom_wall"])}'),
        ('摇杆孔 / 旋钮凸台', f'Ø{f1(jy[4])} / Ø{f1(d0[4])} ×2 (含指针凸出 {f1(H["dial_proud"])})'),
        ('天线', f'展开 {f1(H["ant_span"])}，球头 Ø{f1(H["ant_ball_d"])}，顶 Z{f1(H["ant_top"])}'),
        ('转轴', f'Ø{f1(H["pivot_d"])} @ Y{f1(H["pivot"][1])} Z{f1(H["pivot"][2])}，凸耳宽 {f1(H["lug_w"])}'),
    ]
    cv.text(tx, ty, '机头实测特征', 12, '#7dd3fc', weight='bold')
    for i, (k, v) in enumerate(rows):
        cv.text(tx, ty + 22 + i * 19, k, 11, '#94a3b8')
        cv.text(tx + 150, ty + 22 + i * 19, v, 11, INK)

    # ==========================================================================
    # [B] BASE + KNOB
    # ==========================================================================
    S2 = 2.6
    panel(cv, 20, 748, 1060, 556, '[B]', '底座 wio_tilt_tv_base.stl  +  旋钮 wio_tilt_tv_knob.stl',
          f'底座 {f1(B["ext"][0])} × {f1(B["ext"][1])} × {f1(B["ext"][2])}，{B["vol"]:.2f} cm³ ≈{B["vol"] * DENSITY:.1f} g  |  '
          f'旋钮 Ø{f1(K["ext"][0])} × {f1(K["ext"][2])}，{K["vol"]:.2f} cm³  |  比例 {S2}:1')

    pbf = Projection([base], VIEWS['front'])
    vbf = ViewFrame(cv, pbf, 70 - B['lo'][0] * S2 + 20, 840 + B['hi'][2] * S2 + 20, S2)
    vbf.draw(['base'])
    vbf.center(0, B['pivot'][2], 9)
    vbf.hdim(B['lo'][0], B['hi'][0], -7, 0, 0, label=f1(B['ext'][0]), below=True)
    vbf.vdim(0, B['hi'][2], B['lo'][0] - 6, B['lo'][0], B['arm_l'][0], label=f1(B['ext'][2]))
    vbf.vdim(0, B['pivot'][2], B['lo'][0] + 8, None, -1, label=f'轴高 {f1(B["pivot"][2])}', left=False)
    vbf.hdim(B['arm_l'][1], B['arm_r'][0], B['hi'][2] + 5, B['hi'][2] - 2, B['hi'][2] - 2,
             label=f'{f1(B["gap"])}')
    vbf.hdim(B['arm_l'][0], B['arm_r'][1], B['hi'][2] + 14, B['hi'][2], B['hi'][2],
             label=f'{f1(B["arm_r"][1] - B["arm_l"][0])}')
    vbf.vdim(0, B['plate_top'], B['hi'][0] + 6, B['hi'][0], B['hi'][0], label=f1(B['plate_top']), left=False)
    vbf.note(B['arm_r'][1], B['pivot'][2] + 4, vbf.xy(B['hi'][0], 0)[0] - 10, vbf.xy(0, B['hi'][2] + 3)[1],
             f'臂厚 {f1(B["arm_r"][1] - B["arm_r"][0])}')
    view_label(cv, vbf.xy(0, 0)[0], vbf.xy(0, 0)[1] + 50, '主视图 FRONT')

    pbs = Projection([base], VIEWS['right'])
    vbs = ViewFrame(cv, pbs, 0, vbf.oy, S2)
    vbs.ox = 330 - B['lo'][1] * S2 + 30
    vbs.draw(['base'])
    vbs.center(B['pivot'][1], B['pivot'][2], B['arm_r_round'] + 3)
    vbs.hdim(B['lo'][1], B['hi'][1], -7, 0, 0, label=f1(B['ext'][1]), below=True)
    vbs.hdim(B['lo'][1], B['pivot'][1], B['hi'][2] + 6, B['plate_top'], B['hi'][2],
             label=f'前 {f1(B["pivot"][1] - B["lo"][1])}')
    vbs.hdim(B['pivot'][1], B['hi'][1], B['hi'][2] + 6, None, B['plate_top'],
             label=f'后 {f1(B["hi"][1] - B["pivot"][1])}')
    vbs.note(B['pivot'][1] + 1.2, B['pivot'][2] + 1.2, vbs.xy(B['hi'][1], 0)[0] - 40, vbs.xy(0, B['hi'][2] - 4)[1],
             f'轴孔 Ø{f1(B["pivot_d"])} · 臂顶 R{f1(B["arm_r_round"])}')
    vbs.note(B['hi'][1] - 4, B['plate_top'] - 1, vbs.xy(B['hi'][1], 0)[0] - 40, vbs.xy(0, 15)[1],
             f'底板 {f1(B["plate_top"])}（底腔虚线）', HID)
    view_label(cv, vbs.xy(6, 0)[0], vbs.xy(0, 0)[1] + 50, '右视图 RIGHT')

    pbt = Projection([base], VIEWS['top'])
    vbt = ViewFrame(cv, pbt, vbf.ox, 0, S2)
    vbt.oy = 1000 + B['hi'][1] * S2 + 10
    vbt.draw(['base'], hidden=False)
    vbt.cline(B['lo'][0] - 3, B['pivot'][1], B['hi'][0] + 3, B['pivot'][1])
    vbt.vdim(B['lo'][1], B['hi'][1], B['lo'][0] - 6, B['lo'][0], B['lo'][0], label=f1(B['ext'][1]))
    vbt.note(B['arm_l'][0], B['pivot'][1] - 2, vbt.xy(B['lo'][0], 0)[0] + 6, vbt.xy(0, B['lo'][1] + 10)[1],
             f'六角螺母槽 {f1(B["hex"][4])} 深 {f1(B["hex_depth"])}')
    view_label(cv, vbt.xy(0, 0)[0], vbt.xy(0, B['lo'][1])[1] + 24, '俯视图 TOP')

    pbb = Projection([base], VIEWS['bottom'])
    vbb = ViewFrame(cv, pbb, 0, vbt.oy, S2)
    vbb.ox = 455
    vbb.oy = vbt.oy - (B['hi'][1] + B['lo'][1]) * S2  # same vertical band as the top view
    vbb.draw(['base'], hidden=False)
    if B['feet']:
        ft = B['feet'][0]
        vbb.hdim(ft[0], ft[2], -ft[3] - 3, None, None, label=f'垫槽 {f1(ft[4])}', below=True)
    pe = B['pocket_env']
    vbb.hdim(pe[0], pe[2], -B['hi'][1] - 3, None, None, label=f'减重腔 {f1(pe[4])}×{f1(pe[5])}', below=True)
    vbb.note(0.0, -B['pivot'][1] - 14, vbb.xy(B['hi'][0], 0)[0] + 4, vbb.xy(0, -B['pivot'][1] - 18)[1],
             f'十字筋 {f1(B["rib_w"])}', ACC)
    view_label(cv, vbb.xy(0, 0)[0], vbb.xy(0, -B['hi'][1])[1] + 40, '仰视图 BOTTOM' + (f'（垫槽深 {f1(B["foot_depth"])}）' if B['feet'] else f'（触桌面积 {B["contact"] / 100:.1f} cm²，无独立垫槽）'))

    # Knob: top + side
    S3 = 3.4
    pkt = Projection([knob], VIEWS['bottom'])
    vkt = ViewFrame(cv, pkt, 760, 905, S3)
    vkt.draw(['knob'], hidden=False)
    vkt.center(0, 0, K['ext'][0] / 2 + 3)
    vkt.hdim(K['lo'][0], K['hi'][0], K['lo'][1] - 4, None, None, label=f'Ø{f1(K["ext"][0])}', below=True)
    view_label(cv, vkt.xy(0, 0)[0], vkt.xy(0, K['lo'][1])[1] + 36, f'旋钮底视 · {K["ridges"]} 道防滑筋')
    vkt.note(K['hex'][2], 0, vkt.xy(K['hi'][0], 0)[0] + 10, vkt.xy(0, 7)[1] - 30,
             f'六角 {f1(K["hex"][4])}', ACC)
    pks = Projection([knob], VIEWS['front'])
    vks = ViewFrame(cv, pks, 960, 935, S3)
    vks.draw(['knob'])
    vks.cline(0, -2, 0, K['hi'][2] + 2)
    vks.vdim(0, K['hi'][2], K['lo'][0] - 4, K['lo'][0], -K['collar_d'] / 2, label=f1(K['ext'][2]))
    vks.vdim(0, K['body_h'], K['hi'][0] + 4, K['hi'][0], K['hi'][0], label=f1(K['body_h']), left=False)
    vks.hdim(-K['collar_d'] / 2, K['collar_d'] / 2, K['hi'][2] + 4, K['hi'][2], K['hi'][2],
             label=f'Ø{f1(K["collar_d"])}')
    view_label(cv, vks.xy(0, 0)[0], vks.xy(0, 0)[1] + 40, '旋钮侧视（虚线孔）')
    cv.text(780, 1010, f'内孔 Ø{f1(K["bore"])} · 底部六角穴 {f1(K["hex"][4])}（对边 {f1(K["hex"][5])}）深 {f1(K["hex_depth"])}', 10.5, '#94a3b8')
    cv.text(780, 1027, f'底座右臂沉孔 Ø{f1(B["cbore_d"])} 深 {f1(B["cbore_depth"])}，左臂六角槽 '
                       f'{f1(B["hex"][4])} 深 {f1(B["hex_depth"])}', 10.5, '#94a3b8')

    # ==========================================================================
    # [C] ASSEMBLY
    # ==========================================================================
    panel(cv, 1092, 96, 688, 1208, '[C]', '装配 / 俯仰 / 干涉检查',
          '机头转轴孔对准底座转轴孔（两孔均为实测圆心），绕 X 轴后仰')

    # Iso shaded product view at 20 deg tilt
    h20, b20, k20 = assemble(head, base, knob, M, 20)
    piso = Projection([h20, b20, k20], iso_view(-38, 22))
    Si = 2.8
    viso = ViewFrame(cv, piso, 0, 0, Si)
    lo, hi = piso.lo, piso.hi
    viso.ox = 1092 + 344 - (lo[0] + hi[0]) / 2 * Si
    viso.oy = 160 + hi[1] * Si
    viso.draw_shaded(['head', 'base', 'knob'])
    cv.text(1110, 160, '等轴测着色（后仰 20°，网格直接渲染）', 11, '#94a3b8')

    # Side view: 0 deg solid + 45 deg ghost + clash highlight
    h0, b0, k0 = assemble(head, base, knob, M, 0)
    h45, _, _ = assemble(head, base, knob, M, 45)
    Ss = 2.7
    pside = Projection([h0, b0, k0], VIEWS['right'])
    vs = ViewFrame(cv, pside, 1092 + 300 - 0 * Ss, 0, Ss)
    vs.ox = 1092 + 344 - ((B['lo'][1] + B['hi'][1]) / 2) * Ss
    vs.oy = 868
    pg = Projection([h45], VIEWS['right'])
    vg = ViewFrame(cv, pg, vs.ox, vs.oy, Ss)
    cv.add(f'<path d="{vg.poly_path(pg.silhouette(0))}" fill="{ACC}" fill-opacity="0.07" stroke="{ACC}" '
           f'stroke-width="1" stroke-dasharray="5 3" fill-rule="evenodd"/>')
    vs.draw(['head', 'base', 'knob'], hidden=False)
    for t, ccol in ((0, BAD),):
        vol, inter = clash[t]
        if vol > 0:
            pi = Projection([inter], VIEWS['right'])
            vi = ViewFrame(cv, pi, vs.ox, vs.oy, Ss)
            cv.add(f'<path d="{vi.poly_path(pi.silhouette(0))}" fill="{ccol}" stroke="{ccol}" stroke-width="1.5"/>')
            ib = inter.bounds
            qx, qy = vs.xy((ib[0][1] + ib[1][1]) / 2, (ib[0][2] + ib[1][2]) / 2)
            cv.add(f'<circle cx="{qx:.1f}" cy="{qy:.1f}" r="13" fill="none" stroke="{ccol}" stroke-width="1.4"/>')
            cv.add(f'<polyline points="{qx - 13:.1f},{qy:.1f} {qx - 60:.1f},{qy - 30:.1f} {qx - 150:.1f},{qy - 30:.1f}" '
                   f'fill="none" stroke="{ccol}" stroke-width="0.8"/>')
            cv.text(qx - 150, qy - 34, f'干涉 {clash_mm:.2f} mm（{vol:.1f} mm³）', 11, ccol, weight='bold')
    vs.center(bp[1], bp[2], 10)
    # arc showing tilt travel of the screen top-front corner
    top_front = np.array([0, 0, H['cab_z'][1]]) - np.array(H['pivot']) + bp
    rr = math.hypot(top_front[1] - bp[1], top_front[2] - bp[2])
    a0 = math.atan2(top_front[2] - bp[2], top_front[1] - bp[1])
    x0, y0 = vs.xy(bp[1] + rr * math.cos(a0), bp[2] + rr * math.sin(a0))
    x1, y1 = vs.xy(bp[1] + rr * math.cos(a0 - math.radians(45)), bp[2] + rr * math.sin(a0 - math.radians(45)))
    cv.add(f'<path d="M{x0:.1f} {y0:.1f}A{rr * Ss:.1f} {rr * Ss:.1f} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" '
           f'stroke="{ACC}" stroke-width="1.2" marker-end="url(#ar)"/>')
    cv.text(x1 + 6, y1 - 6, '0° → 45°', 11, ACC, weight='bold')
    total_h = h0.bounds[1][2]
    vs.vdim(0, total_h, B['lo'][1] - 40, B['lo'][1], H['cab_y'][0] - H['pivot'][1] + bp[1],
            label=f'装配总高 {f1(total_h)}')
    vs.vdim(0, bp[2], B['hi'][1] + 6, B['hi'][1], bp[1], label=f'轴高 {f1(bp[2])}', left=False)
    # tipping margin at 45 deg: centre of mass of head+base vs footprint
    com45 = (h45.center_mass * h45.volume + base.center_mass * base.volume) / (h45.volume + base.volume)
    cx_, cy_ = vs.xy(com45[1], com45[2])
    cv.add(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" fill="none" stroke="{OK}" stroke-width="1.5"/>'
           f'<line x1="{cx_:.1f}" y1="{cy_:.1f}" x2="{cx_:.1f}" y2="{vs.xy(0, 0)[1]:.1f}" stroke="{OK}" '
           f'stroke-width="0.8" stroke-dasharray="3 2"/>')
    margin = B['hi'][1] - com45[1]
    cv.text(cx_ + 8, cy_ + 4, f'45° 重心 Y{com45[1]:+.1f}', 10.5, OK)
    view_label(cv, vs.xy(6, 0)[0], vs.oy + 30, '右视装配：实线 0°，橙虚线 45°，红色 = 干涉体')

    # Check list
    cy = 935
    cv.text(1110, cy, '装配实测校核', 13, '#7dd3fc', weight='bold')
    checks = []
    gap_c = (B['gap'] - H['lug_w']) / 2
    checks.append((gap_c > 0, f'凸耳 {f1(H["lug_w"])} 入叉口 {f1(B["gap"])}：单侧间隙 {gap_c:.2f}'))
    checks.append((abs(H['pivot_d'] - B['pivot_d']) < 0.5,
                   f'转轴孔 机头 Ø{f1(H["pivot_d"])} / 底座 Ø{f1(B["pivot_d"])}（M3 螺栓）'))
    span = B['arm_r'][1] - B['arm_l'][0]
    checks.append((True, f'叉臂外宽 {f1(span)} + 旋钮 {f1(K["ext"][2])} = {f1(span + K["ext"][2])}（螺栓长度参考）'))
    vmax = max(v for v, _ in clash.values())
    checks.append((vmax < 1e-3, f'机头⇄底座干涉：' + ' / '.join(f'{t}° {clash[t][0]:.1f}mm³' for t in tilt_samples)))
    checks.append((clash_mm <= 0, f'臂顶圆角 R{f1(B["arm_r_round"])} vs 轴心到机身底面 {f1(pivot_to_cab)}：' +
                   (f'间隙 {-clash_mm:.2f}' if clash_mm <= 0 else f'重叠 {clash_mm:.2f}')))
    checks.append((H['web'] >= 0.8, f'屏幕窗 ⇄ 摇杆孔 间隔 {H["web"]:.2f}（嘉立创最小壁厚 0.8）'))
    checks.append((bool(B['feet']), '底面防滑垫槽：' + (f'{len(B["feet"])} 个' if B['feet'] else
                                                     '网格中不存在（落入减重腔被吞掉）')))
    checks.append((margin > 0, f'45° 后仰合重心距后缘 {f1(margin)}（不含 Wio 本体）'))
    for name, d in (('机头', H), ('底座', B), ('旋钮', K)):
        checks.append((d['watertight'] and d['shells'] == 1 and max(d['ext']) <= 100,
                       f'{name}：水密 {"✓" if d["watertight"] else "✗"} · 壳体 {d["shells"]} · '
                       f'最大边 {f1(max(d["ext"]))} ≤ 100'))
    jlc = H['vol'] + B['vol']
    checks.append((jlc <= 70, f'嘉立创免费：机头+底座 {jlc:.2f} cm³ ≤ 70'))
    for i, (ok, s) in enumerate(checks):
        yy = cy + 26 + i * 21
        cv.text(1112, yy, '✓' if ok else '✗', 13, OK if ok else BAD, weight='bold')
        cv.text(1132, yy, s, 11, INK if ok else '#fda4af')

    cv.add('</svg>')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cv.out))

    # Print the measurement report for cross-checking
    for name in ('head', 'base', 'knob'):
        print(f'--- {name} ---')
        for k, v in M[name].items():
            if isinstance(v, (tuple, list, np.ndarray)):
                v = tuple(round(float(x), 2) if isinstance(x, (int, float, np.floating)) else x for x in np.ravel(v)) \
                    if not (isinstance(v, list) and v and isinstance(v[0], tuple)) else [tuple(round(x, 2) for x in t) for t in v]
            elif isinstance(v, float):
                v = round(v, 3)
            print(f'  {k:14s} {v}')
    print('clash mm3:', {t: round(v, 2) for t, (v, _) in clash.items()}, 'overlap', round(clash_mm, 2))
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    build()
