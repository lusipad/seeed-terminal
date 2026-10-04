"""
render_preview.py - Renders cad/preview_render.jpg (product shot) straight from the STL meshes.

Software renderer built on the z-buffer of generate_svg_preview.Projection:
per-pixel Lambert + Blinn shading, a shadow map from the key light, depth/crease outlines
and 2x supersampling. A plain 72 x 57 x 12 Wio Terminal block is placed in the rear pocket
so the screen window shows a lit display.

Usage (from repo root):  python tools/render_preview.py
"""

import math
import os
import sys

import numpy as np
import trimesh
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from generate_svg_preview import STL_DIR, Projection, assemble, head_pose, iso_view, measure  # noqa: E402

OUT = 'cad/preview_render.jpg'
TILT = 15.0
VIEW = iso_view(-34, 22)
RES = 0.055                 # mm per supersampled pixel
LIGHT = np.array([-0.45, -0.65, 0.95])
FILL = np.array([0.8, -0.3, 0.35])

# Wio Terminal stand-in (head coordinates): 72 x 57 x 12 against the front stop at Y=2.2
WIO_BOX = ([-36.0, 2.3, 3.5], [36.0, 14.3, 60.5])
WIO_SCREEN = (-5.0, 32.0, 48.96, 36.72)     # centre x, centre z, active width, height

ALBEDO = {
    'head': (0.93, 0.90, 0.83),
    'base': (0.30, 0.32, 0.36),
    'knob': (0.80, 0.58, 0.27),
    'wio': (0.10, 0.11, 0.13),
    'ground': (0.90, 0.89, 0.86),
}
SPEC = {'head': 0.25, 'base': 0.35, 'knob': 0.7, 'wio': 0.4, 'ground': 0.0}
BG_TOP = np.array([0.95, 0.94, 0.92])
BG_BOT = np.array([0.84, 0.83, 0.80])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def screen_pattern(x, z):
    """Pixel-pet face on a blue-teal gradient; x, z in head mm, returns RGB in 0..1."""
    cx, cz, w, h = WIO_SCREEN
    u = (x - (cx - w / 2)) / w          # 0..1 left to right
    v = (z - (cz - h / 2)) / h          # 0..1 bottom to top
    col = np.stack([0.05 + 0.10 * v, 0.30 + 0.35 * v, 0.55 + 0.30 * v], -1)
    # chunky 320x240-ish pixels, scaled up 8x
    gx, gy = np.floor(u * 40), np.floor((1 - v) * 30)
    eye = ((np.abs(gx - 14) <= 1) | (np.abs(gx - 25) <= 1)) & (gy >= 10) & (gy <= 13)
    mouth = (gy == 19) & (gx >= 16) & (gx <= 23) | (gy == 18) & ((gx == 15) | (gx == 24))
    cheek = ((np.abs(gx - 11) <= 1) | (np.abs(gx - 28) <= 1)) & (gy == 16)
    col = np.where((eye | mouth)[..., None], np.array([0.97, 0.98, 1.0]), col)
    col = np.where(cheek[..., None], np.array([1.0, 0.55, 0.65]), col)
    return col


def main():
    head = trimesh.load(f'{STL_DIR}/wio_tilt_tv_head.stl')
    base = trimesh.load(f'{STL_DIR}/wio_tilt_tv_base.stl')
    knob = trimesh.load(f'{STL_DIR}/wio_tilt_tv_knob.stl')
    M = measure(head, base, knob)
    h, b, k = assemble(head, base, knob, M, TILT)
    pose = head_pose(M, TILT)
    wio = trimesh.creation.box(bounds=WIO_BOX)
    stick = trimesh.creation.cylinder(radius=3.2, segment=[[27.0, 2.3, 16.0], [27.0, 0.6, 16.0]], sections=32)
    wio = trimesh.util.concatenate([wio, stick])       # z-buffer only, no boolean needed
    wio.apply_transform(pose)

    objs = [h, b, k, wio]
    kinds = ['head', 'base', 'knob', 'wio']

    # Frame: object bounds in view space + margins; ground plane filling the frame
    R = np.array(VIEW, float)
    pts = np.vstack([m.vertices @ R.T for m in objs])
    lo, hi = pts[:, :2].min(0), pts[:, :2].max(0)
    span = hi - lo
    lo = lo - np.array([0.22, 0.12]) * span[0]
    hi = hi + np.array([0.22, 0.10]) * span[0]
    ground = trimesh.creation.box(bounds=[[-400, -400, -2.0], [400, 400, -0.02]])

    proj = Projection(objs + [ground], VIEW, res=RES, bounds=(lo, hi))
    kinds = kinds + ['ground']
    H, W = proj.zbuf.shape
    print(f'render {W}x{H} px (supersampled)')

    # Pixel -> world position and normal
    gx, gy = np.meshgrid((np.arange(W) + 0.5) * RES + lo[0], (np.arange(H) + 0.5) * RES + lo[1])
    hit = proj.fbuf >= 0
    d = np.where(hit, proj.zbuf, 0.0)
    world = np.stack([gx, gy, d], -1) @ R          # rows of R are u, v, w -> world = [u v w] @ R
    mi = np.where(hit, proj.fbuf >> 32, -1)
    fi = np.where(hit, proj.fbuf & 0xffffffff, 0)
    nrm = np.zeros((H, W, 3))
    alb = np.zeros((H, W, 3))
    spec = np.zeros((H, W))
    for i, (m, kind) in enumerate(zip(proj.meshes, kinds)):
        sel = mi == i
        nrm[sel] = m.face_normals[fi[sel]]
        alb[sel] = ALBEDO[kind]
        spec[sel] = SPEC[kind]

    # Shadow map from the key light (objects only)
    L = unit(LIGHT)
    lu = unit(np.cross([0, 0, 1], L))
    lview = (tuple(lu), tuple(np.cross(L, lu)), tuple(L))
    sproj = Projection(objs, lview, res=0.12)
    lp = world.reshape(-1, 3) @ np.array(lview, float).T
    ix = np.clip(((lp[:, 0] - sproj.lo[0]) / sproj.res).astype(int), 0, sproj.zbuf.shape[1] - 1)
    iy = np.clip(((lp[:, 1] - sproj.lo[1]) / sproj.res).astype(int), 0, sproj.zbuf.shape[0] - 1)
    inside = (lp[:, 0] >= sproj.lo[0]) & (lp[:, 0] <= sproj.hi[0]) & (lp[:, 1] >= sproj.lo[1]) & (lp[:, 1] <= sproj.hi[1])
    lit = ~(inside & (lp[:, 2] < sproj.zbuf[iy, ix] - 0.35))
    lit = lit.reshape(H, W).astype(float)
    lit_img = Image.fromarray((lit * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=10))
    lit = np.asarray(lit_img, float) / 255.0

    # Lighting
    V = unit(R[2])
    ndl = np.clip(nrm @ L, 0, 1)
    ndf = np.clip(nrm @ unit(FILL), 0, 1)
    hv = unit(L + V)
    sp = np.clip(nrm @ hv, 0, 1) ** 40
    sky = 0.5 + 0.5 * nrm[..., 2]
    shade = 0.30 + 0.16 * sky + 0.62 * ndl * lit + 0.18 * ndf
    col = alb * shade[..., None] + (spec * sp * lit)[..., None] * 0.9

    # Wio display: emissive where the stand-in's front face shows through the window
    inv = np.linalg.inv(pose)
    wsel = mi == 3
    if wsel.any():
        local = (np.c_[world[wsel], np.ones(wsel.sum())] @ inv.T)[:, :3]
        n_local = nrm[wsel] @ inv[:3, :3].T
        cx, cz, sw, sh = WIO_SCREEN
        face = (n_local[:, 1] < -0.9) & (np.abs(local[:, 0] - cx) < sw / 2) & (np.abs(local[:, 2] - cz) < sh / 2)
        emis = screen_pattern(local[:, 0], local[:, 2])
        c = col[wsel]
        c[face] = emis[face] * 0.92 + 0.06
        col[wsel] = c

    # Ground: fade into the backdrop, keep the contact shadow
    gsel = mi == len(objs)
    dist = np.linalg.norm(world[..., :2] - np.array([0.0, 6.0]), axis=-1)
    fade = np.clip((dist - 45) / 70, 0, 1)
    vgrad = (np.arange(H)[:, None] / H)                  # 0 bottom .. 1 top (v grows upward)
    bg = np.broadcast_to(BG_BOT + (BG_TOP - BG_BOT) * vgrad[..., None], (H, W, 3))
    gcol = bg * (0.62 + 0.38 * lit)[..., None]
    gcol = gcol * (1 - fade[..., None]) + bg * fade[..., None]
    col[gsel] = gcol[gsel]
    col[~hit] = bg[~hit]

    # Outlines: depth jumps and creases between object pixels
    obj = hit & ~gsel
    dz = np.zeros((H, W))
    dn = np.zeros((H, W))
    for ax in (0, 1):
        dz = np.maximum(dz, np.abs(np.diff(d, axis=ax, prepend=d[:1] if ax == 0 else d[:, :1])))
        nn = np.diff(nrm, axis=ax, prepend=nrm[:1] if ax == 0 else nrm[:, :1])
        dn = np.maximum(dn, np.linalg.norm(nn, axis=-1))
    edge = obj & ((dz > 1.2) | (dn > 0.9))
    col[edge] *= 0.45

    img = np.clip(col, 0, 1) ** (1 / 1.05)
    im = Image.fromarray((img[::-1] * 255).astype(np.uint8))   # row 0 = top
    im = im.resize((W // 2, H // 2), Image.LANCZOS)
    im.save(OUT, quality=92)
    print('wrote', OUT, im.size, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
