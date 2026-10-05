"""
generate_svg_preview.py - Renders cad/tilt_tv_product_preview.svg straight from the STL meshes.

Nothing in the drawing is hand-typed geometry:
  * every outline is a projected mesh edge (sharp edges + view silhouettes),
    split into visible / hidden runs with a z-buffer (hidden-line removal);
  * every dimension value is measured on the mesh (bounding boxes, plane
    sections, ray probes) and printed to stdout for cross-checking;
  * the assembly pose maps the measured hinge bore of the monitor onto the base's,
    and every tilt step is checked for interference by mesh intersection.

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
FILL = {'head': '#1e293b', 'cover': '#1a2638', 'base': '#172235', 'bottom': '#14202f', 'panel': '#111827',
        'knob': '#26303f'}
SHADE = {'head': (236, 232, 222), 'cover': (226, 222, 211), 'base': (236, 232, 222), 'bottom': (215, 211, 200),
         'panel': (52, 56, 62), 'knob': (62, 66, 72)}


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
PARTS = ['head', 'rear_cover', 'base', 'bottom_cover', 'front_panel', 'knob']
NAMES = {'head': '显示器前壳', 'rear_cover': 'CRT 后盖', 'base': '主机盒', 'bottom_cover': '底盖',
         'front_panel': '正面面板', 'knob': '阻尼旋钮'}
KINDS = ['head', 'cover', 'base', 'bottom', 'panel', 'knob']


def load_parts():
    return {n: trimesh.load(f'{STL_DIR}/wio_tilt_tv_{n}.stl') for n in PARTS}


def x_bore(mesh, x, near, max_d=6.0):
    """Centre (y, z) and diameter of the round hole in the section x = const nearest a point."""
    sec = section(mesh, [x, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))
    hs = [bbox2(h) for h in holes(sec) if bbox2(h)[4] < max_d]
    best = min(hs, key=lambda b: math.hypot(b[6] - near[0], b[7] - near[1]))
    return best[6], best[7], (best[4] + best[5]) / 2


def measure(P):
    M = {}
    for n, m in P.items():
        M[n] = dict(lo=m.bounds[0], hi=m.bounds[1], ext=m.extents, vol=m.volume / 1000.0,
                    shells=len(m.split(only_watertight=False)), watertight=m.is_watertight)
    H, C, B, BC, FP, K = (M[n] for n in PARTS)
    head, cover, base, bot, panel_m, knob = (P[n] for n in PARTS)

    # Head: see-through openings in the front view (screen window, joystick)
    hs = holes(Projection([head], VIEWS['front']).silhouette(0))
    H['screen'], H['joy'] = bbox2(hs[0]), bbox2(hs[1])
    H['web'] = H['joy'][0] - H['screen'][2]
    H['dials'] = sorted([bbox2(d) for d in parts(section(head, [0, -1.0, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1)))
                         if bbox2(d)[4] > 5], key=lambda b: -b[7])
    xs = ray_hits(head, np.array([-200.0, 13.0, 40.0]), [1, 0, 0])
    H['body_w'] = xs[-1] - xs[0]
    H['side_wall'] = xs[1] - xs[0]
    zs = ray_hits(head, np.array([-20.0, 1.5, -50.0]), [0, 0, 1])
    H['bezel_z'] = (zs[0] - 50.0, zs[-1] - 50.0)
    ys = ray_hits(head, np.array([0.0, -50.0, 56.0]), [0, 1, 0])
    H['front_wall'] = ys[1] - ys[0]
    H['pocket_front_y'] = ys[1] - 50.0
    rear = section(head, [0, 25.7, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1))
    H['pocket'] = bbox2(holes(rear)[0])
    # Probe the side wall (outside the open-backed pocket) for the body's back face
    H['body_back_y'] = 200.0 - ray_hits(head, np.array([H['lo'][0] + 3.5, 200.0, 40.0]), [0, -1, 0])[0]
    # Floor openings (section through the 2mm floor)
    fl = sorted([bbox2(h) for h in holes(section(head, [0, 0, 2.0], [0, 0, 1], (1, 0, 0), (0, 1, 0)))],
                key=lambda b: -b[4] * b[5])
    H['port_slot'] = fl[0]
    H['wire_holes'] = sorted(fl[1:3], key=lambda b: b[6])
    # Hinge: bore in the tail knuckle, tail width
    hy, hz, hd = x_bore(head, 0.0, (H['hi'][1] - 4.0, H['lo'][2] + 4.0))
    H['axis'], H['bore_d'] = (0.0, hy, hz), hd
    xs = ray_hits(head, np.array([-200.0, hy, hz + 3.0]), [1, 0, 0])
    H['tail_w'] = xs[-1] - xs[0]
    H['knuckle_r'] = hz - H['lo'][2]

    # Rear cover
    C['depth'] = C['hi'][1] - H['body_back_y']
    C['vents'] = len(holes(section(cover, [0, C['hi'][1] - 0.6, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1))))

    # Base
    B['top'] = 100.0 - ray_hits(base, np.array([-40.0, -50.0, 100.0]), [0, 0, -1])[0]
    B['step'] = 100.0 - ray_hits(base, np.array([25.0, 5.0, 100.0]), [0, 0, -1])[0]
    # Knuckles: the bore section on a plane through the right knuckle, near the top rear
    xs = [x - 200.0 for x in ray_hits(base, np.array([-200.0, 0.0, B['step'] + 9.5]), [1, 0, 0])]
    kn = [x for x in xs if abs(x) < 20]
    B['knuckles'] = tuple(kn[:4])
    B['gap'] = kn[2] - kn[1]
    by, bz, bd = x_bore(base, (kn[2] + kn[3]) / 2, (0.0, B['step'] + 6.0))
    B['axis'], B['bore_d'] = (0.0, by, bz), bd
    xs = [x - 200.0 for x in ray_hits(base, np.array([-200.0, by + 6.0, B['step'] + 3.0]), [1, 0, 0])]
    B['bay'] = (xs[1], xs[-2])
    # Top-plate openings (clip off the hinge-bay end so the tail slot reads as a closed opening)
    top_sec = section(base, [0, 0, B['top'] - 1.0], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    clip = Polygon([(-60, -80), (60, -80), (60, by - 10.5), (-60, by - 10.5)])
    gaps = top_sec.convex_hull.intersection(clip).difference(top_sec)
    tops = sorted([bbox2(g) for g in parts(gaps) if g.area > 20.0], key=lambda b: (b[7], b[6]))
    B['top_holes'] = tops
    fw = holes(section(base, [0, base.bounds[0][1] + 1.0, 0], [0, 1, 0], (1, 0, 0), (0, 0, 1)))
    B['window'] = bbox2(fw[0])
    B['grille'] = len(holes(section(base, [base.bounds[0][0] + 1.0, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))))
    B['vents'] = len(holes(section(base, [base.bounds[1][0] - 1.0, 0, 0], [1, 0, 0], (0, 1, 0), (0, 0, 1))))
    cb = ray_hits(base, np.array([-30.0, by + 2.4, bz]), [1, 0, 0])      # from inside the hinge bay
    B['cbore_depth'] = cb[0] - 30.0 - B['knuckles'][0]

    # Bottom cover: battery bay and standoffs from a slice above the plate
    sl = section(bot, [0, 0, BC['lo'][2] + 3.5], [0, 0, 1], (1, 0, 0), (0, 1, 0))
    BC['bay'] = bbox2(holes(sl)[0])
    posts = [bbox2(p) for p in parts(sl) if bbox2(p)[4] < 8]
    BC['posts'] = sorted(posts, key=lambda b: (b[7], b[6]))
    BC['post_pitch'] = min(abs(a[6] - b[6]) for a in posts for b in posts if abs(a[6] - b[6]) > 1)
    BC['feet'] = len([h for h in holes(section(bot, [0, 0, 0.3], [0, 0, 1], (1, 0, 0), (0, 1, 0))) if h.area > 50])
    BC['plate_t'] = 100.0 - ray_hits(bot, np.array([30.0, -40.0, 100.0]), [0, 0, -1])[0]

    # Front panel cut-outs, matched to the generator's port names by position
    import generate_3d_models as G
    ph = [bbox2(h) for h in holes(Projection([panel_m], VIEWS['front']).silhouette(0))]
    names = list(G.FRONT_PORTS) + [('LED', G.FRONT_LED[0], G.FRONT_LED[1], 0, 0, 0)]
    FP['ports'] = []
    for b in sorted(ph, key=lambda b: b[6]):
        n = min(names, key=lambda p: math.hypot(p[1] - b[6], p[2] - b[7]))[0]
        FP['ports'].append((n, b))

    K['bore'] = bbox2(holes(section(knob, [0, 0, 5.0], [0, 0, 1], (1, 0, 0), (0, 1, 0)))[0])[4]
    K['hex'] = bbox2(holes(section(knob, [0, 0, 0.3], [0, 0, 1], (1, 0, 0), (0, 1, 0)))[0])
    K['hex_depth'] = ray_hits(knob, np.array([0.0, 2.4, -10.0]), [0, 0, 1])[0] - 10.0
    return M


def pose_from(M, tilt_deg):
    """Head / rear cover -> assembled pose: measured head bore onto measured base bore, tilted back."""
    T = trimesh.transformations.translation_matrix(np.subtract(M['base']['axis'], M['head']['axis']))
    return trimesh.transformations.rotation_matrix(math.radians(-tilt_deg), [1, 0, 0], M['base']['axis']) @ T


def assembly(P, M, tilt_deg):
    import generate_3d_models as G
    T = pose_from(M, tilt_deg)
    h, c = P['head'].copy(), P['rear_cover'].copy()
    h.apply_transform(T)
    c.apply_transform(T)
    k = P['knob'].copy()
    k.apply_transform(G.knob_pose())
    return [h, c, P['base'].copy(), P['bottom_cover'].copy(), P['front_panel'].copy(), k]


def inter_vol(a, b):
    i = trimesh.boolean.intersection([a, b], engine='manifold')
    return i.volume if len(i.faces) else 0.0


def table(cv, x, y, title, rows, kw=110):
    cv.text(x, y, title, 12, '#7dd3fc', weight='bold')
    for i, (k_, v_) in enumerate(rows):
        cv.text(x, y + 22 + i * 19, k_, 11, '#94a3b8')
        cv.text(x + kw, y + 22 + i * 19, v_, 10.5, INK)


def build():
    P = load_parts()
    M = measure(P)
    H, C, B, BC, FP, K = (M[n] for n in PARTS)

    # ---------------- assembly checks ----------------
    tilts = list(range(0, 50, 5))
    clash = {}
    for t in tilts:
        A = assembly(P, M, t)
        clash[t] = sum(inter_vol(mv, ms) for mv in A[:2] for ms in A[2:])
    A0 = assembly(P, M, 0)
    A45 = assembly(P, M, 45)
    static_pairs = [('盒/底盖', 2, 3), ('盒/面板', 2, 4), ('底盖/面板', 3, 4), ('盒/旋钮', 2, 5)]
    static_clash = {n: inter_vol(A0[i], A0[j]) for n, i, j in static_pairs}
    v = A0[0].vertices
    v = v[(np.abs(v[:, 0]) > 8.0) & (v[:, 1] < B['axis'][1] - 10.0)]     # monitor floor, excluding the tail
    rest_gap = v[:, 2].min() - B['top']
    knob_clear = A0[5].bounds[0][2] - B['step']
    tail_side = (B['gap'] - H['tail_w']) / 2
    # Bolt: from the counterbore floor (left knuckle) to the far face of the knob's nut pocket
    bolt = (A0[5].bounds[0][0] + K['hex_depth']) - (B['knuckles'][0] + B['cbore_depth'])
    vols = [m.volume for m in A45[:5]]
    com45 = sum(m.center_mass * m.volume for m in A45[:5]) / sum(vols)
    foot = (P['base'].bounds[0][1], P['base'].bounds[1][1])

    W, HH = 1800, 1420
    cv = Canvas()
    cv.add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HH}" width="{W}" height="{HH}" '
           f'font-family="Consolas, \'Microsoft YaHei\', \'PingFang SC\', monospace">')
    cv.add('<defs><marker id="ar" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 1.5L10 5L0 8.5z" fill="#38bdf8"/></marker>'
           '<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse">'
           '<path d="M20 0H0V20" fill="none" stroke="#111a2b" stroke-width="0.6"/></pattern></defs>')
    cv.add(f'<rect width="{W}" height="{HH}" fill="#0a0f1d"/><rect width="{W}" height="{HH}" fill="url(#g)"/>')
    cv.text(28, 40, 'WIO TERMINAL 复古桌面显示器 — STL 实测视图 / 装配 / 扩展预留', 22, '#f8fafc', weight='bold')
    cv.text(28, 62, '单位 mm  |  各视图观察方向见图名  |  轮廓 = STL 网格边投影 + z-buffer 消隐（实线可见 / 虚线隐藏）  |  '
                    '尺寸 = 网格截面 / 射线实测', 11.5, '#94a3b8')
    cv.text(28, 80, 'source: cad/stl/wio_tilt_tv_*.stl（6 个零件） — regenerate: python tools/generate_3d_models.py ; '
                    'python tools/generate_svg_preview.py', 11, '#475569')

    # ======================= [A] monitor =======================
    S = 2.4
    panel(cv, 20, 96, 1060, 610, '[A]', '显示器：前壳 head + CRT 后盖 rear_cover',
          f'前壳 {f1(H["ext"][0])}×{f1(H["ext"][1])}×{f1(H["ext"][2])} · {H["vol"]:.2f} cm³  |  '
          f'后盖 {f1(C["ext"][0])}×{f1(C["ext"][1])}×{f1(C["ext"][2])} · {C["vol"]:.2f} cm³  |  比例 {S}:1')
    head = P['head']
    vf = ViewFrame(cv, Projection([head], VIEWS['front']), 0, 0, S)
    vf.ox, vf.oy = 105 - H['lo'][0] * S, 165 + H['hi'][2] * S
    vf.draw(['head'])
    sw, jy = H['screen'], H['joy']
    vf.center(sw[6], sw[7], sw[4] / 2 + 3)
    vf.center(jy[6], jy[7], jy[4] / 2 + 3)
    bz0, bz1 = H['bezel_z']
    vf.hdim(H['lo'][0], H['hi'][0], H['lo'][2] - 5, bz0, bz0, label=f1(H['ext'][0]), below=True)
    vf.hdim(sw[0], sw[2], sw[3] + 4, sw[3], sw[3], label=f'窗 {f1(sw[4])}')
    vf.vdim(sw[1], sw[3], sw[0] - 4, sw[0], sw[0], label=f1(sw[5]))
    vf.vdim(bz0, bz1, H['lo'][0] - 6, H['lo'][0], H['lo'][0], label=f1(bz1 - bz0))
    vf.vdim(H['lo'][2], bz1, H['lo'][0] - 17, -H['tail_w'] / 2, H['lo'][0], label=f'含铰链 {f1(bz1 - H["lo"][2])}')
    vf.note(jy[6] + 3, jy[7] - 3, vf.xy(H['hi'][0], 0)[0] + 14, vf.xy(0, jy[7] - 8)[1], f'摇杆孔 Ø{f1(jy[4])}')
    d0 = H['dials'][0]
    vf.note(d0[6] + 3, d0[7] + 3, vf.xy(H['hi'][0], 0)[0] + 14, vf.xy(0, d0[7] + 8)[1], f'旋钮凸台 Ø{f1(d0[4])} ×2')
    vf.note(29.0, 57.5, vf.xy(H['hi'][0], 0)[0] + 14, vf.xy(0, 68)[1], 'RGB 指示点 ×3')
    view_label(cv, vf.xy(0, 0)[0], vf.xy(0, H['lo'][2])[1] + 44, '主视图 FRONT')

    pr = Projection([head, P['rear_cover']], VIEWS['right'])
    vr = ViewFrame(cv, pr, 0, vf.oy, S)
    vr.ox = 470 - H['lo'][1] * S
    vr.draw(['head', 'cover'])
    ax = H['axis']
    vr.center(ax[1], ax[2], H['knuckle_r'] + 3)
    vr.hdim(H['lo'][1], H['hi'][1], H['lo'][2] - 5, None, None, label=f1(H['ext'][1]), below=True)
    vr.hdim(0, H['body_back_y'], bz1 + 5, bz1, bz1, label=f'前壳 {f1(H["body_back_y"])}')
    vr.hdim(H['body_back_y'], C['hi'][1], bz1 + 5, None, C['hi'][2], label=f'后盖 {f1(C["depth"])}')
    vr.note(ax[1] + 1.2, ax[2] - 1.2, vr.xy(H['hi'][1], 0)[0] + 16, vr.xy(0, ax[2] - 6)[1],
            f'铰链孔 Ø{f1(H["bore_d"])} · 尾宽 {f1(H["tail_w"])}')
    vr.note(H['pocket_front_y'] + 13, 50, vr.xy(H['hi'][1], 0)[0] + 16, vr.xy(0, 56)[1], 'U 形插唇顶住 Wio', HID)
    view_label(cv, vr.xy(20, 0)[0], vr.xy(0, H['lo'][2])[1] + 44, '右视图 RIGHT（前壳 + 后盖）')

    pc = Projection([P['rear_cover']], VIEWS['rear'])
    vc = ViewFrame(cv, pc, 900, vf.oy, S)
    vc.draw(['cover'])
    vc.hdim(-C['hi'][0], -C['lo'][0], C['lo'][2] - 6, None, None, label=f1(C['ext'][0]), below=True)
    vc.vdim(C['lo'][2], C['hi'][2], -C['hi'][0] - 6, None, None, label=f1(C['ext'][2]))
    view_label(cv, vc.xy(0, 0)[0], vc.xy(0, H['lo'][2])[1] + 44, f'后盖后视（{C["vents"]} 道散热槽）')

    pb = Projection([head], VIEWS['bottom'])
    vb = ViewFrame(cv, pb, vf.ox, 0, S)
    vb.oy = 475
    vb.draw(['head'], hidden=False)
    ps = H['port_slot']
    vb.hdim(ps[0], ps[2], -ps[1] + 4, -ps[1], -ps[1], label=f'底边接口槽 {f1(ps[4])}×{f1(ps[5])}')
    wh = H['wire_holes'][1]
    for w_ in H['wire_holes']:
        vb.center(w_[6], -w_[7], 3)
    vb.note(wh[2] - 1, -wh[7], vb.xy(H['hi'][0], 0)[0] + 14, vb.xy(0, -wh[7] + 2)[1], f'40-Pin 走线孔 ×2')
    vb.note(ps[2] - 2, -ps[7], vb.xy(H['hi'][0], 0)[0] + 14, vb.xy(0, -ps[7] + 9)[1], 'USB-C + 2×Grove 直插向下')
    view_label(cv, vb.xy(0, 0)[0], vb.xy(0, -H['hi'][1])[1] + 22, '仰视图 BOTTOM（线缆直通主机盒）')

    pk = H['pocket']
    table(cv, 600, 500, '显示器实测特征', [
        ('屏幕视窗', f'{f1(sw[4])} × {f1(sw[5])}，中心 X{sw[6]:+.1f} Z{f1(sw[7])}'),
        ('Wio 插口', f'{f1(pk[4])} × {f1(pk[5])}（Wio 72×57×12），前挡壁 {f1(H["front_wall"])}'),
        ('侧壁 / 窗-摇杆', f'{f1(H["side_wall"])} / {f1(H["web"])}'),
        ('底边接口槽', f'{f1(ps[4])} × {f1(ps[5])}（USB-C + 2×Grove）'),
        ('40-Pin 走线孔', f'{f1(wh[4])} × {f1(wh[5])} ×2'),
        ('铰链', f'Ø{f1(H["bore_d"])} @ Y{f1(ax[1])} Z{f1(ax[2])}（机身后下方）'),
    ])

    # ======================= [B] base =======================
    S2 = 2.3
    panel(cv, 20, 718, 1060, 690, '[B]', '主机盒 base + 底盖 bottom_cover + 正面面板 front_panel + 旋钮 knob',
          f'主机盒 {f1(B["ext"][0])}×{f1(B["ext"][1])}×{f1(B["ext"][2])} · {B["vol"]:.2f} cm³  |  '
          f'底盖 {BC["vol"]:.2f} cm³  |  面板 {FP["vol"]:.2f} cm³  |  旋钮 Ø{f1(K["ext"][0])}×{f1(K["ext"][2])}  |  比例 {S2}:1')
    base, bot = P['base'], P['bottom_cover']
    kn = A0[5]
    pbf = Projection([base, bot, P['front_panel'], kn], VIEWS['front'])
    vbf = ViewFrame(cv, pbf, 105 - B['lo'][0] * S2, 800 + 32 * S2, S2)
    vbf.draw(['base', 'bottom', 'panel', 'knob'], hidden=False)
    vbf.hdim(B['lo'][0], B['hi'][0], -6, 0, 0, label=f1(B['ext'][0]), below=True)
    vbf.vdim(0, B['top'], B['lo'][0] - 6, B['lo'][0], B['lo'][0], label=f1(B['top']))
    win = B['window']
    vbf.hdim(win[0], win[2], B['top'] + 4, win[3], win[3], label=f'面板窗 {f1(win[4])}×{f1(win[5])}')
    view_label(cv, vbf.xy(0, 0)[0], vbf.xy(0, 0)[1] + 40, '主视图 FRONT（装面板 + 底盖）')

    pbs = Projection([base, bot, kn], VIEWS['right'])
    vbs = ViewFrame(cv, pbs, 0, vbf.oy, S2)
    vbs.ox = 420 - B['lo'][1] * S2
    vbs.draw(['base', 'bottom', 'knob'], hidden=False)
    vbs.center(B['axis'][1], B['axis'][2], 7)
    vbs.hdim(B['lo'][1], B['hi'][1], -6, 0, 0, label=f1(B['ext'][1]), below=True)
    vbs.vdim(0, B['axis'][2], B['hi'][1] + 6, B['axis'][1], None, label=f'轴高 {f1(B["axis"][2])}', left=False)
    view_label(cv, vbs.xy(-25, 0)[0], vbs.xy(0, 0)[1] + 40, f'右视图 RIGHT（{B["vents"]} 道竖向散热槽）')

    S3 = 3.0
    pfp = Projection([P['front_panel']], VIEWS['front'])
    vfp = ViewFrame(cv, pfp, 815, vbf.oy - 4 * S3, S3)
    vfp.draw(['panel'])
    for i, (n, b) in enumerate(FP['ports']):
        lx, ly = vfp.xy(b[6], FP['lo'][2])
        dy = 14 if i % 2 == 0 else 38
        cv.text(lx, ly + dy, n, 10, ACC, 'middle', 'bold')
        cv.text(lx, ly + dy + 12, f'{f1(b[4])}×{f1(b[5])}' if n != 'LED' else f'Ø{f1(b[4])}', 9.5, '#94a3b8', 'middle')
    vfp.hdim(FP['lo'][0], FP['hi'][0], FP['hi'][2] + 3, FP['hi'][2], FP['hi'][2], label=f1(FP['ext'][0]))
    view_label(cv, vfp.xy(0, 0)[0], vfp.xy(0, FP['hi'][2])[1] - 30, '正面面板（可换）· 默认开孔')

    pbt = Projection([base, kn], VIEWS['top'])
    vbt = ViewFrame(cv, pbt, vbf.ox, 0, S2)
    vbt.oy = 1010 + B['hi'][1] * S2 + 30
    vbt.draw(['base', 'knob'], hidden=False)
    vbt.vdim(B['lo'][1], B['hi'][1], B['lo'][0] - 6, B['lo'][0], B['lo'][0], label=f1(B['ext'][1]))
    vbt.cline(B['lo'][0] - 3, B['axis'][1], B['hi'][0] + 3, B['axis'][1])
    th = B['top_holes']
    big = max(th, key=lambda b: b[4] * b[5])
    vbt.note(big[2] - 3, big[7], vbt.xy(B['hi'][0], 0)[0] + 10, vbt.xy(0, big[7] + 8)[1], f'走线口 ×{len(th)}')
    vbt.hdim(B['bay'][0], B['bay'][1], B['hi'][1] + 4, B['hi'][1], B['hi'][1], label=f'铰链槽 {f1(B["bay"][1] - B["bay"][0])}')
    view_label(cv, vbt.xy(0, 0)[0], vbt.xy(0, B['lo'][1])[1] + 30, '俯视图 TOP')

    pbc = Projection([bot], VIEWS['top'])
    vbc = ViewFrame(cv, pbc, 0, vbt.oy, S2)
    vbc.ox = 445 - BC['lo'][0] * S2
    vbc.draw(['bottom'], hidden=False)
    bay = BC['bay']
    vbc.hdim(bay[0], bay[2], bay[3] + 3, bay[3], bay[3], label=f'电池仓 {f1(bay[4])}×{f1(bay[5])}')
    for p_ in BC['posts']:
        vbc.center(p_[6], p_[7], 4)
    view_label(cv, vbc.xy(0, 0)[0], vbc.xy(0, BC['lo'][1])[1] + 30,
               f'底盖内侧（模块柱 ×{len(BC["posts"])}，间距 {f1(BC["post_pitch"])}）')

    table(cv, 800, 1010, '扩展预留（实测）', [
        ('接口面板窗', f'{f1(win[4])} × {f1(win[5])}；面板 {f1(FP["ext"][0])}×{f1(FP["ext"][2])} 从底部插入'),
        ('顶面走线口', f'{len(th)} 个（Wio 底边接口 / 40-Pin / 铰链尾）'),
        ('喇叭格栅', f'左侧 {B["grille"]} 孔 + 内侧卡槽（3520 腔体喇叭）'),
        ('散热槽', f'右侧 {B["vents"]} 道'),
        ('电池仓', f'{f1(bay[4])} × {f1(bay[5])}（603040 / 503040）'),
        ('模块柱', f'{len(BC["posts"])} 根 · {f1(BC["post_pitch"])} 网格（Grove 模块 M2）'),
        ('底盖', f'{BC["plate_t"]:.1f} 厚 · 4 颗 M3 沉头自攻 · 垫槽 ×{BC["feet"]}'),
        ('铰链', f'孔 Ø{f1(B["bore_d"])} · 叉口 {f1(B["gap"])} · M3×25'),
    ], kw=82)

    # ======================= [C] assembly =======================
    panel(cv, 1092, 96, 688, 1312, '[C]', '装配 / 俯仰 / 干涉检查',
          '显示器绕机身后下方的铰链轴后仰：前沿抬起，不会扫进主机盒')
    piso = Projection(A0, iso_view(-32, 20))
    Si = 3.0
    viso = ViewFrame(cv, piso, 0, 0, Si)
    lo, hi = piso.lo, piso.hi
    viso.ox = 1092 + 344 - (lo[0] + hi[0]) / 2 * Si
    viso.oy = 175 + hi[1] * Si
    viso.draw_shaded(KINDS)
    cv.text(1110, 160, '等轴测着色（0°，网格直接渲染）', 11, '#94a3b8')

    Ss = 2.8
    pside = Projection(A0, VIEWS['right'])
    vs = ViewFrame(cv, pside, 0, 0, Ss)
    vs.ox = 1092 + 330 - ((foot[0] + foot[1]) / 2) * Ss
    vs.oy = 930
    pg = Projection(A45[:2], VIEWS['right'])
    vg = ViewFrame(cv, pg, vs.ox, vs.oy, Ss)
    ghost = unary_union([pg.silhouette(0), pg.silhouette(1)])
    cv.add(f'<path d="{vg.poly_path(ghost)}" fill="{ACC}" fill-opacity="0.07" stroke="{ACC}" '
           f'stroke-width="1" stroke-dasharray="5 3" fill-rule="evenodd"/>')
    vs.draw(KINDS, hidden=False)
    bax = B['axis']
    vs.center(bax[1], bax[2], 8)
    fz = A0[0].bounds[1][2]
    vs.vdim(0, fz, foot[0] - 8, foot[0], None, label=f'总高 {f1(fz)}')
    vs.vdim(0, bax[2], foot[1] + 8, foot[1], bax[1], label=f'轴高 {f1(bax[2])}', left=False)
    # Arc traced by the top-front corner of the bezel
    tf = np.array([0.0, A0[0].bounds[0][1], A0[0].bounds[1][2]])
    r_ = math.hypot(tf[1] - bax[1], tf[2] - bax[2])
    a0 = math.atan2(tf[2] - bax[2], tf[1] - bax[1])
    x0, y0 = vs.xy(bax[1] + r_ * math.cos(a0), bax[2] + r_ * math.sin(a0))
    x1, y1 = vs.xy(bax[1] + r_ * math.cos(a0 - math.radians(45)), bax[2] + r_ * math.sin(a0 - math.radians(45)))
    cv.add(f'<path d="M{x0:.1f} {y0:.1f}A{r_ * Ss:.1f} {r_ * Ss:.1f} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" '
           f'stroke="{ACC}" stroke-width="1.2" marker-end="url(#ar)"/>')
    cv.text(x1 + 6, y1 - 4, '0° → 45°', 11, ACC, weight='bold')
    cx_, cy_ = vs.xy(com45[1], com45[2])
    cv.add(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" fill="none" stroke="{OK}" stroke-width="1.5"/>'
           f'<line x1="{cx_:.1f}" y1="{cy_:.1f}" x2="{cx_:.1f}" y2="{vs.xy(0, 0)[1]:.1f}" stroke="{OK}" '
           f'stroke-width="0.8" stroke-dasharray="3 2"/>')
    cv.text(cx_ + 8, cy_ - 6, '45° 重心', 10.5, OK)
    view_label(cv, vs.xy((foot[0] + foot[1]) / 2, 0)[0], vs.oy + 30, '右视装配：实线 0°，橙虚线 45°')

    cy = 1000
    cv.text(1110, cy, '装配实测校核', 13, '#7dd3fc', weight='bold')
    checks = []
    vmax = max(clash.values())
    checks.append((vmax < 1e-3, f'俯仰 0°~45° 每 5° 求交：最大干涉 {vmax:.2f} mm³'))
    checks.append((all(x < 1e-3 for x in static_clash.values()),
                   '零件互配 ' + ' · '.join(f'{k_} {x:.1f}' for k_, x in static_clash.items()) + ' mm³'))
    checks.append((-0.01 <= rest_gap < 1.0, f'0° 显示器底面离盒顶 {rest_gap:.2f}（坐稳不悬空）'))
    checks.append((tail_side > 0, f'铰链尾 {f1(H["tail_w"])} 入叉口 {f1(B["gap"])}：单侧间隙 {tail_side:.2f}'))
    checks.append((abs(H['bore_d'] - B['bore_d']) < 0.5, f'铰链孔 显示器 Ø{f1(H["bore_d"])} / 主机盒 Ø{f1(B["bore_d"])}'))
    checks.append((knob_clear > 0, f'旋钮离铰链槽底 {knob_clear:.2f}'))
    checks.append((bolt <= 25.0, f'螺栓夹持长度 {bolt:.1f} → M3×25（沉孔 {f1(B["cbore_depth"])} · 螺母穴 {f1(K["hex_depth"])}）'))
    checks.append((foot[0] < com45[1] < foot[1], f'45° 打印件合重心 Y{com45[1]:+.1f}，底座 Y{foot[0]:.0f}~{foot[1]:+.0f}（不含 Wio）'))
    checks.append((H['web'] >= 0.8, f'屏幕窗 ⇄ 摇杆孔 间隔 {H["web"]:.2f}（≥0.8）'))
    for n in PARTS:
        d = M[n]
        checks.append((d['watertight'] and d['shells'] == 1,
                       f'{NAMES[n]}：水密 {"✓" if d["watertight"] else "✗"} · 壳体 {d["shells"]} · '
                       f'{f1(d["ext"][0])}×{f1(d["ext"][1])}×{f1(d["ext"][2])} · {d["vol"]:.2f} cm³'))
    total = sum(M[n]['vol'] for n in PARTS)
    checks.append((True, f'合计 {total:.2f} cm³ ≈ {total * DENSITY:.0f} g（9600 树脂）'))
    for i, (ok, s_) in enumerate(checks):
        yy = cy + 26 + i * 21
        cv.text(1112, yy, '✓' if ok else '✗', 13, OK if ok else BAD, weight='bold')
        cv.text(1132, yy, s_, 10.5, INK if ok else '#fda4af')

    cv.add('</svg>')
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cv.out))

    for n in PARTS:
        print(f'--- {n} ---')
        for k_, v_ in M[n].items():
            print(f'  {k_:14s} {np.round(v_, 2).tolist() if isinstance(v_, np.ndarray) else v_}')
    print('clash', {t: round(x, 3) for t, x in clash.items()}, 'static', static_clash)
    print('rest_gap', round(rest_gap, 3), 'knob_clear', round(knob_clear, 2), 'bolt', round(bolt, 2),
          'com45', np.round(com45, 1))
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    build()
