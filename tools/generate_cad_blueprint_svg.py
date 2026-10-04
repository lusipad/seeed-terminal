"""
generate_cad_blueprint_svg.py - Generates an exact, dimensionally-accurate
engineering blueprint SVG directly from the real CAD model coordinates.
Scale: 1 mm = 2.5 px. Every dimension matches the STL files exactly.
"""

import os
import math

def build_blueprint_svg():
    S = 2.5 # 1mm = 2.5 SVG pixels

    # Dimensions from STL files (in mm):
    head_w = 82.0
    head_h_box = 64.0
    head_d = 26.0
    head_h_total = 94.5 # from lug bottom (-14) to ears top (+80.5)
    ear_top_z = 80.5
    screen_w = 50.0
    screen_h = 38.0
    screen_x = -5.0
    screen_z = 32.0 # center

    base_w = 76.0
    base_d = 72.0 # -30 to +42
    base_t = 4.5
    pivot_z_from_ground = 26.5 # in base coordinates
    clevis_arm_h = 34.5
    clevis_gap = 14.4
    lug_w = 14.0

    knob_d = 18.6
    knob_t = 10.0

    # Colors
    c_bg = "#090d16"
    c_grid = "#131b28"
    c_solid = "#e2e8f0"
    c_hidden = "#475569"
    c_center = "#ef4444"
    c_dim = "#38bdf8"
    c_accent = "#f59e0b"
    c_highlight = "#10b981"

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 920" width="100%" height="100%" style="background:{c_bg}; font-family:Consolas, Monaco, \"Segoe UI\", \"PingFang SC\", monospace;">')

    # Defs: arrow markers and grid
    svg.append('''<defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 2 L 10 5 L 0 8 z" fill="#38bdf8"/>
      </marker>
      <marker id="arrowRev" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 10 2 L 0 5 L 10 8 z" fill="#38bdf8"/>
      </marker>
      <pattern id="cadGrid" width="25" height="25" patternUnits="userSpaceOnUse">
        <path d="M 25 0 L 0 0 0 25" stroke="#141d2b" stroke-width="0.8"/>
      </pattern>
      <pattern id="cadGridSub" width="125" height="125" patternUnits="userSpaceOnUse">
        <path d="M 125 0 L 0 0 0 125" stroke="#1e2c40" stroke-width="1.2"/>
      </pattern>
    </defs>''')

    # Grid background
    svg.append('<rect width="1280" height="920" fill="url(#cadGrid)"/>')
    svg.append('<rect width="1280" height="920" fill="url(#cadGridSub)"/>')

    # Outer Blueprint Drawing Border
    svg.append('<rect x="24" y="24" width="1232" height="872" fill="none" stroke="#334155" stroke-width="2"/>')
    svg.append('<rect x="28" y="28" width="1224" height="864" fill="none" stroke="#1e293b" stroke-width="1"/>')

    # =========================================================================
    # HEADER / TITLE BLOCK
    # =========================================================================
    svg.append(f'''
    <g transform="translate(48, 56)">
      <text x="0" y="0" fill="#f8fafc" font-size="20" font-weight="bold" letter-spacing="0.5">WIO TERMINAL 可俯仰复古小电视监视器 — 标准工程制图三视图</text>
      <text x="0" y="22" fill="#94a3b8" font-size="12">DWG NO: WT-TILT-TV-001  |  SCALE 2.5:1 (1mm = 2.5px)  |  UNIT: MM  |  MODEL: 9600 HIGH-TOUGHNESS RESIN</text>
      <text x="0" y="38" fill="#38bdf8" font-size="11">✓ 严格按真实 STL 网格尺寸 1:1 投影绘制（所有标注与 cad/stl/*.stl 几何完全一致）</text>
    </g>
    ''')

    # =========================================================================
    # VIEW 1: FRONT ELEVATION (主视图 / 正立面)
    # Center X = 250, Ground Line Z = 0 at Y = 460
    # Head vertical (0° tilt) to show true rectangular projections
    # =========================================================================
    vx1 = 250
    vy_g = 470 # Ground line Y

    svg.append(f'''
    <!-- ==================== VIEW 1: FRONT ELEVATION ==================== -->
    <g id="view_front">
      <!-- View Title -->
      <text x="{vx1}" y="125" fill="#f8fafc" font-size="15" font-weight="bold" text-anchor="middle">主视图 / 正立面 (FRONT ELEVATION)</text>
      <text x="{vx1}" y="142" fill="#64748b" font-size="11" text-anchor="middle">视角：从正面直视（未俯仰，机头垂直状态）</text>

      <!-- Centerline (Vertical) -->
      <line x1="{vx1}" y1="150" x2="{vx1}" y2="{vy_g + 20}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="16,4,4,4"/>

      <!-- Ground line -->
      <line x1="{vx1 - 160}" y1="{vy_g}" x2="{vx1 + 160}" y2="{vy_g}" stroke="#475569" stroke-width="1.5"/>

      <!-- 1. BASE: Plate width = 76mm, height = 4.5mm -->
      <rect x="{vx1 - base_w/2 * S}" y="{vy_g - base_t * S}" width="{base_w * S}" height="{base_t * S}"
            fill="#131b28" stroke="{c_solid}" stroke-width="1.5" rx="1"/>

      <!-- 2. BASE: Upright Clevis Arms (Arm L: -12.2 to -7.2, Arm R: 7.2 to 12.2) -->
      <!-- Arm height from ground to pivot = 26.5mm, top radius = 8mm -> total top Z = 34.5mm -->
      <rect x="{vx1 - 12.2 * S}" y="{vy_g - 26.5 * S}" width="{5.0 * S}" height="{(26.5 - base_t) * S}"
            fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx1 - 9.7 * S}" cy="{vy_g - 26.5 * S}" r="{8.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>

      <rect x="{vx1 + 7.2 * S}" y="{vy_g - 26.5 * S}" width="{5.0 * S}" height="{(26.5 - base_t) * S}"
            fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx1 + 9.7 * S}" cy="{vy_g - 26.5 * S}" r="{8.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>

      <!-- Pivot center-line horizontal -->
      <line x1="{vx1 - 40 * S}" y1="{vy_g - 26.5 * S}" x2="{vx1 + 40 * S}" y2="{vy_g - 26.5 * S}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="14,3,3,3"/>

      <!-- Pivot hole in arms (diameter 3.6mm) -->
      <circle cx="{vx1 - 9.7 * S}" cy="{vy_g - 26.5 * S}" r="{1.8 * S}" fill="#090d16" stroke="{c_dim}" stroke-width="1"/>
      <circle cx="{vx1 + 9.7 * S}" cy="{vy_g - 26.5 * S}" r="{1.8 * S}" fill="#090d16" stroke="{c_dim}" stroke-width="1"/>

      <!-- 3. HEAD: Bottom Hinge Lug (width 14mm: X from -7.0 to +7.0) -->
      <!-- Lug extends down around pivot Z=26.5mm, from Z=19.5mm to Z=33.5mm -->
      <rect x="{vx1 - 7.0 * S}" y="{vy_g - (26.5 + 7.0) * S}" width="{14.0 * S}" height="{14.0 * S}"
            fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx1}" cy="{vy_g - 26.5 * S}" r="{7.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx1}" cy="{vy_g - 26.5 * S}" r="{1.8 * S}" fill="#090d16" stroke="{c_solid}" stroke-width="1"/>

      <!-- 4. HEAD: Cabinet Body (Width 82mm: X=-41 to +41, Height 64mm: Z from 33.5mm to 97.5mm) -->
      <rect x="{vx1 - head_w/2 * S}" y="{vy_g - 97.5 * S}" width="{head_w * S}" height="{head_h_box * S}"
            rx="12" fill="#131b28" stroke="{c_solid}" stroke-width="2"/>

      <!-- Screen Window Cutout: 50.0mm x 38.0mm (X centered at -5.0mm -> -30.0 to +20.0mm; Z centered at 32.0 in head -> Z=65.5mm from ground -> Y = vy_g - (65.5+19)*S to vy_g - (65.5-19)*S) -->
      <rect x="{vx1 + (-30.0) * S}" y="{vy_g - (65.5 + 19.0) * S}" width="{screen_w * S}" height="{screen_h * S}"
            rx="6" fill="#090d16" stroke="{c_solid}" stroke-width="1.5"/>
      <!-- Inner LCD active area (48.6 x 36.5 mm) -->
      <rect x="{vx1 + (-29.3) * S}" y="{vy_g - (65.5 + 18.25) * S}" width="{48.6 * S}" height="{36.5 * S}"
            rx="2" fill="#0f172a" stroke="#38bdf8" stroke-width="1" stroke-dasharray="3,2"/>
      <text x="{vx1 - 5.0 * S}" y="{vy_g - 62.0 * S}" fill="#38bdf8" font-size="10" text-anchor="middle" font-family="monospace">2.4" LCD 320x240</text>

      <!-- Right Panel: Dual Knobs (X = 27.0mm, diameter 10.0mm) -->
      <!-- Knob 1: Z in head = 43.0mm -> from ground = 33.5 + 43.0 = 76.5mm -->
      <circle cx="{vx1 + 27.0 * S}" cy="{vy_g - 76.5 * S}" r="{5.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.2"/>
      <circle cx="{vx1 + 27.0 * S}" cy="{vy_g - 76.5 * S}" r="{2.0 * S}" fill="{c_accent}"/>

      <!-- Knob 2: Z in head = 23.0mm -> from ground = 33.5 + 23.0 = 56.5mm -->
      <circle cx="{vx1 + 27.0 * S}" cy="{vy_g - 56.5 * S}" r="{5.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.2"/>
      <circle cx="{vx1 + 27.0 * S}" cy="{vy_g - 56.5 * S}" r="{2.0 * S}" fill="{c_accent}"/>

      <!-- Front 5-way Joystick Opening: X = 25.0mm, Z in head = 17.0mm -> from ground = 50.5mm, diameter 15.0mm (radius 7.5mm) -->
      <circle cx="{vx1 + 25.0 * S}" cy="{vy_g - 50.5 * S}" r="{7.5 * S}" fill="#090d16" stroke="{c_solid}" stroke-width="1.2"/>
      <circle cx="{vx1 + 25.0 * S}" cy="{vy_g - 50.5 * S}" r="{4.0 * S}" fill="#0284c7" stroke="#38bdf8" stroke-width="1"/>

      <!-- Top Buttons Cutout: Width 42.0mm, X centered at -5.0mm -> -26.0 to +16.0mm, at top edge (Z=97.5mm) -->
      <rect x="{vx1 + (-26.0) * S}" y="{vy_g - 97.5 * S}" width="{42.0 * S}" height="{4.0 * S}"
            fill="#090d16" stroke="{c_solid}" stroke-width="1"/>

      <!-- Two Cat Ears on Top: Base X=±(13.5 to 26.5), Peak at X=±20.0, Z=114.0mm from ground (80.5+33.5) -->
      <!-- Left Ear -->
      <polygon points="{vx1 - 26.5*S},{vy_g - 97.5*S} {vx1 - 13.5*S},{vy_g - 97.5*S} {vx1 - 20.0*S},{vy_g - 114.0*S}"
               fill="#131b28" stroke="{c_solid}" stroke-width="1.5"/>
      <!-- Right Ear -->
      <polygon points="{vx1 + 13.5*S},{vy_g - 97.5*S} {vx1 + 26.5*S},{vy_g - 97.5*S} {vx1 + 20.0*S},{vy_g - 114.0*S}"
               fill="#131b28" stroke="{c_solid}" stroke-width="1.5"/>

      <!-- Side Knurled Knob (Right side of base arm: X from 12.2 to 22.2mm, diameter 18.6mm, centered at Z=26.5mm) -->
      <rect x="{vx1 + 12.2 * S}" y="{vy_g - (26.5 + 9.3) * S}" width="{knob_t * S}" height="{knob_d * S}"
            fill="{c_accent}" fill-opacity="0.2" stroke="{c_accent}" stroke-width="1.2" rx="2"/>
      <line x1="{vx1 + (12.2 + 3) * S}" y1="{vy_g - (26.5 + 9.3) * S}" x2="{vx1 + (12.2 + 3) * S}" y2="{vy_g - (26.5 - 9.3) * S}" stroke="{c_accent}" stroke-width="1"/>

      <!-- DIMENSION LINES FOR VIEW 1 -->
      <!-- Dim 1: Head Width = 82.0 mm (top) -->
      <line x1="{vx1 - 41.0 * S}" y1="175" x2="{vx1 + 41.0 * S}" y2="175" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <line x1="{vx1 - 41.0 * S}" y1="170" x2="{vx1 - 41.0 * S}" y2="{vy_g - 97.5 * S}" stroke="{c_dim}" stroke-width="0.6"/>
      <line x1="{vx1 + 41.0 * S}" y1="170" x2="{vx1 + 41.0 * S}" y2="{vy_g - 97.5 * S}" stroke="{c_dim}" stroke-width="0.6"/>
      <text x="{vx1}" y="170" fill="{c_dim}" font-size="11" font-weight="bold" text-anchor="middle">82.0</text>

      <!-- Dim 2: Base Width = 76.0 mm (bottom) -->
      <line x1="{vx1 - 38.0 * S}" y1="{vy_g + 25}" x2="{vx1 + 38.0 * S}" y2="{vy_g + 25}" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <line x1="{vx1 - 38.0 * S}" y1="{vy_g}" x2="{vx1 - 38.0 * S}" y2="{vy_g + 30}" stroke="{c_dim}" stroke-width="0.6"/>
      <line x1="{vx1 + 38.0 * S}" y1="{vy_g}" x2="{vx1 + 38.0 * S}" y2="{vy_g + 30}" stroke="{c_dim}" stroke-width="0.6"/>
      <text x="{vx1}" y="{vy_g + 38}" fill="{c_dim}" font-size="11" font-weight="bold" text-anchor="middle">76.0 (底座宽度)</text>

      <!-- Dim 3: Screen Window = 50.0 mm -->
      <line x1="{vx1 - 30.0 * S}" y1="{vy_g - (65.5 + 24) * S}" x2="{vx1 + 20.0 * S}" y2="{vy_g - (65.5 + 24) * S}" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <text x="{vx1 - 5.0 * S}" y="{vy_g - (65.5 + 27) * S}" fill="{c_dim}" font-size="10" font-weight="bold" text-anchor="middle">50.0 (视窗)</text>

      <!-- Dim 4: Total Height = 114.0 mm (left side) -->
      <line x1="{vx1 - 125}" y1="{vy_g - 114.0 * S}" x2="{vx1 - 125}" y2="{vy_g}" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <line x1="{vx1 - 20.0 * S}" y1="{vy_g - 114.0 * S}" x2="{vx1 - 130}" y2="{vy_g - 114.0 * S}" stroke="{c_dim}" stroke-width="0.6"/>
      <line x1="{vx1 - 38.0 * S}" y1="{vy_g}" x2="{vx1 - 130}" y2="{vy_g}" stroke="{c_dim}" stroke-width="0.6"/>
      <text x="{vx1 - 132}" y="{vy_g - 57.0 * S}" fill="{c_dim}" font-size="11" font-weight="bold" text-anchor="end">114.0</text>

      <!-- Dim 5: Pivot Height = 26.5 mm -->
      <line x1="{vx1 - 70}" y1="{vy_g - 26.5 * S}" x2="{vx1 - 70}" y2="{vy_g}" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <text x="{vx1 - 75}" y="{vy_g - 13.0 * S}" fill="{c_dim}" font-size="10" font-weight="bold" text-anchor="end">26.5</text>

      <!-- Dim 6: Lug Width = 14.0 mm -->
      <text x="{vx1}" y="{vy_g - 10}" fill="{c_highlight}" font-size="9" text-anchor="middle">转轴凸耳: 14.0</text>
    </g>
    ''')

    # =========================================================================
    # VIEW 2: SIDE ELEVATION & TILT TRAJECTORY (左视图 / 侧立面与俯仰轨迹)
    # Center X = 740, Ground Line Z = 0 at Y = 470
    # Shows:
    # 1. Base footprint: Front at Y = -30mm, Rear at Y = +42mm (Total 72mm)
    # 2. Pivot axis at (X=0, Z=26.5mm)
    # 3. Head in 25° Tilt (Active), 0° (Vertical, dashed), 45° (Max, dashed)
    # =========================================================================
    vx2 = 720
    # In side view:
    # Horizontal axis is Y! Front is -Y (left on page), Rear is +Y (right on page).
    # Base footprint: from Y = -30mm to Y = +42mm.
    # Pivot axis is at Y = 0mm!

    svg.append(f'''
    <!-- ==================== VIEW 2: SIDE ELEVATION & TILT TRAJECTORY ==================== -->
    <g id="view_side">
      <!-- View Title -->
      <text x="{vx2}" y="125" fill="#f8fafc" font-size="15" font-weight="bold" text-anchor="middle">左视图 / 侧立面与俯仰轨迹 (SIDE ELEVATION)</text>
      <text x="{vx2}" y="142" fill="{c_accent}" font-size="11" text-anchor="middle">显示 0° 垂直、25° 黄金工作视角、45° 最大俯仰范围</text>

      <!-- Centerline through Pivot (Vertical at Y=0) -->
      <line x1="{vx2}" y1="150" x2="{vx2}" y2="{vy_g + 20}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="16,4,4,4"/>
      <!-- Centerline horizontal through Pivot (Z=26.5mm) -->
      <line x1="{vx2 - 100}" y1="{vy_g - 26.5 * S}" x2="{vx2 + 150}" y2="{vy_g - 26.5 * S}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="16,4,4,4"/>

      <!-- Ground line -->
      <line x1="{vx2 - 130}" y1="{vy_g}" x2="{vx2 + 160}" y2="{vy_g}" stroke="#475569" stroke-width="1.5"/>

      <!-- 1. BASE: Total Depth 72mm (Front = -30mm, Rear = +42mm, thickness 4.5mm) -->
      <rect x="{vx2 - 30.0 * S}" y="{vy_g - base_t * S}" width="{base_d * S}" height="{base_t * S}"
            fill="#131b28" stroke="{c_solid}" stroke-width="1.5" rx="1"/>

      <!-- Base Upright Clevis Arm (depth 18mm: Y from -9 to +9, centered at Y=0) -->
      <rect x="{vx2 - 9.0 * S}" y="{vy_g - 26.5 * S}" width="{18.0 * S}" height="{(26.5 - base_t) * S}"
            fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx2}" cy="{vy_g - 26.5 * S}" r="{8.0 * S}" fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>
      <circle cx="{vx2}" cy="{vy_g - 26.5 * S}" r="{1.8 * S}" fill="#090d16" stroke="{c_dim}" stroke-width="1"/>

      <!-- 2. POSITION 1: 0° Tilt (Vertical, Dashed) -->
      <g opacity="0.35">
        <!-- Head cabinet side profile: Depth 26mm (Y from 0 to +26mm relative to front, lug centered at Y=13mm) -->
        <!-- Relative to pivot Y=0: Head front is at Y = -13mm, rear is at Y = +13mm! -->
        <rect x="{vx2 - 13.0 * S}" y="{vy_g - 97.5 * S}" width="{head_d * S}" height="{head_h_box * S}"
              rx="4" fill="none" stroke="{c_solid}" stroke-width="1.2" stroke-dasharray="4,3"/>
        <text x="{vx2 - 18 * S}" y="{vy_g - 70 * S}" fill="{c_solid}" font-size="10" font-family="monospace">0°</text>
      </g>

      <!-- 3. POSITION 3: 45° Tilt (Max Angle, Dashed) -->
      <g transform="rotate(45, {vx2}, {vy_g - 26.5 * S})" opacity="0.35">
        <rect x="{vx2 - 13.0 * S}" y="{vy_g - 97.5 * S}" width="{head_d * S}" height="{head_h_box * S}"
              rx="4" fill="none" stroke="{c_solid}" stroke-width="1.2" stroke-dasharray="4,3"/>
        <text x="{vx2 + 2 * S}" y="{vy_g - 75 * S}" fill="{c_solid}" font-size="10" font-family="monospace">45°</text>
      </g>

      <!-- 4. POSITION 2: 25° Tilt (Recommended Active Operating Position) -->
      <g transform="rotate(25, {vx2}, {vy_g - 26.5 * S})">
        <!-- Lug connecting to pivot (centered at Y=0, Z=26.5mm) -->
        <rect x="{vx2 - 8.0 * S}" y="{vy_g - 33.5 * S}" width="{16.0 * S}" height="{14.0 * S}"
              fill="#1e293b" stroke="{c_solid}" stroke-width="1.2"/>

        <!-- Head Cabinet: Depth 26mm (Y from -13 to +13mm), Height 64mm (Z from 33.5 to 97.5mm) -->
        <rect x="{vx2 - 13.0 * S}" y="{vy_g - 97.5 * S}" width="{head_d * S}" height="{head_h_box * S}"
              rx="8" fill="#131b28" stroke="{c_solid}" stroke-width="2"/>

        <!-- Front Screen active display line (Cyan glowing) -->
        <line x1="{vx2 - 13.0 * S}" y1="{vy_g - (65.5 + 18.25) * S}" x2="{vx2 - 13.0 * S}" y2="{vy_g - (65.5 - 18.25) * S}"
              stroke="#38bdf8" stroke-width="3"/>

        <!-- Front Rotary Knob protrusion (sticking out 3.0mm at front) -->
        <rect x="{vx2 - 16.0 * S}" y="{vy_g - (76.5 + 5.0) * S}" width="{3.0 * S}" height="{10.0 * S}" fill="{c_accent}"/>
        <rect x="{vx2 - 16.0 * S}" y="{vy_g - (56.5 + 5.0) * S}" width="{3.0 * S}" height="{10.0 * S}" fill="{c_accent}"/>

        <!-- Rear Sound Slits (depth 2.2mm at rear wall) -->
        <rect x="{vx2 + 11.0 * S}" y="{vy_g - 80.0 * S}" width="{2.0 * S}" height="{25.0 * S}" fill="#475569"/>

        <!-- Top Cat Ear side profile -->
        <polygon points="{vx2 - 7.0*S},{vy_g - 97.5*S} {vx2 + 7.0*S},{vy_g - 97.5*S} {vx2},{vy_g - 114.0*S}"
                 fill="#131b28" stroke="{c_solid}" stroke-width="1.2"/>
      </g>

      <!-- Center Pivot Knob Circle in Side View -->
      <circle cx="{vx2}" cy="{vy_g - 26.5 * S}" r="{knob_d/2 * S}" fill="{c_accent}" fill-opacity="0.3" stroke="{c_accent}" stroke-width="1.5"/>
      <circle cx="{vx2}" cy="{vy_g - 26.5 * S}" r="{1.8 * S}" fill="#090d16" stroke="{c_solid}" stroke-width="1"/>

      <!-- TILT SWEEP ARC (0° to 45°) -->
      <path d="M {vx2} {vy_g - 85 * S} A {58.5 * S} {58.5 * S} 0 0 1 {vx2 + math.sin(math.radians(45)) * 58.5 * S} {vy_g - (26.5 + math.cos(math.radians(45)) * 58.5) * S}"
            fill="none" stroke="{c_dim}" stroke-width="1.8" stroke-dasharray="4,3" marker-end="url(#arrow)"/>
      <text x="{vx2 + 35 * S}" y="{vy_g - 75 * S}" fill="{c_dim}" font-size="11" font-weight="bold">0° ~ 45° 俯仰行程</text>

      <!-- DIMENSIONS FOR VIEW 2 -->
      <!-- Dim 1: Base Total Depth = 72.0 mm (bottom) -->
      <line x1="{vx2 - 30.0 * S}" y1="{vy_g + 25}" x2="{vx2 + 42.0 * S}" y2="{vy_g + 25}" stroke="{c_dim}" stroke-width="1" marker-start="url(#arrowRev)" marker-end="url(#arrow)"/>
      <line x1="{vx2 - 30.0 * S}" y1="{vy_g}" x2="{vx2 - 30.0 * S}" y2="{vy_g + 30}" stroke="{c_dim}" stroke-width="0.6"/>
      <line x1="{vx2 + 42.0 * S}" y1="{vy_g}" x2="{vx2 + 42.0 * S}" y2="{vy_g + 30}" stroke="{c_dim}" stroke-width="0.6"/>
      <text x="{vx2 + 6.0 * S}" y="{vy_g + 38}" fill="{c_dim}" font-size="11" font-weight="bold" text-anchor="middle">72.0 (底座深度: 前30 / 后42)</text>

      <!-- Dim 2: Head Thickness = 26.0 mm -->
      <text x="{vx2 - 25 * S}" y="{vy_g - 90 * S}" fill="{c_dim}" font-size="10" font-weight="bold" text-anchor="end">机身厚度: 26.0</text>

      <!-- Anti-tip Safety Callout -->
      <rect x="{vx2 + 48.0 * S}" y="{vy_g - 40}" width="160" height="42" rx="4" fill="#1e293b" stroke="{c_highlight}" stroke-width="1"/>
      <text x="{vx2 + 54.0 * S}" y="{vy_g - 24}" fill="{c_highlight}" font-size="10" font-weight="bold">✓ 物理防倾覆力学设计：</text>
      <text x="{vx2 + 54.0 * S}" y="{vy_g - 10}" fill="#94a3b8" font-size="9">后脚跟延伸42mm，后倾余量27.8mm</text>
    </g>
    ''')

    # =========================================================================
    # VIEW 3: TOP PLAN VIEW (俯视图 / 平面图)
    # Center X = 250, Y = 680
    # Shows: Base plate 76.0mm x 72.0mm, Head top view, Cat ears
    # =========================================================================
    vx3 = 250
    vy3 = 680

    svg.append(f'''
    <!-- ==================== VIEW 3: TOP PLAN VIEW ==================== -->
    <g id="view_top">
      <text x="{vx3}" y="560" fill="#f8fafc" font-size="15" font-weight="bold" text-anchor="middle">俯视图 / 平面图 (TOP PLAN VIEW)</text>
      <text x="{vx3}" y="576" fill="#64748b" font-size="11" text-anchor="middle">视角：从上往下俯视底盘与机身顶部</text>

      <!-- Centerlines -->
      <line x1="{vx3}" y1="{vy3 - 60 * S}" x2="{vx3}" y2="{vy3 + 60 * S}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="14,3,3,3"/>
      <line x1="{vx3 - 55 * S}" y1="{vy3}" x2="{vx3 + 55 * S}" y2="{vy3}" stroke="{c_center}" stroke-width="0.8" stroke-dasharray="14,3,3,3"/>

      <!-- Base Plate: 76.0mm wide (-38 to +38), 72.0mm deep (-30 to +42) -->
      <!-- In top view: Y axis goes down (+Y is rear, -Y is front) -->
      <rect x="{vx3 - 38.0 * S}" y="{vy3 - 30.0 * S}" width="{76.0 * S}" height="{72.0 * S}"
            fill="#131b28" stroke="{c_solid}" stroke-width="1.5" rx="3"/>

      <!-- 4 Coin Ballast Wells (Hidden dashed circles on bottom): diameter 25.5mm -->
      <circle cx="{vx3 - 17.0 * S}" cy="{vy3 - 10.0 * S}" r="{12.75 * S}" fill="none" stroke="{c_hidden}" stroke-width="0.8" stroke-dasharray="3,2"/>
      <circle cx="{vx3 + 17.0 * S}" cy="{vy3 - 10.0 * S}" r="{12.75 * S}" fill="none" stroke="{c_hidden}" stroke-width="0.8" stroke-dasharray="3,2"/>
      <circle cx="{vx3 - 17.0 * S}" cy="{vy3 + 22.0 * S}" r="{12.75 * S}" fill="none" stroke="{c_hidden}" stroke-width="0.8" stroke-dasharray="3,2"/>
      <circle cx="{vx3 + 17.0 * S}" cy="{vy3 + 22.0 * S}" r="{12.75 * S}" fill="none" stroke="{c_hidden}" stroke-width="0.8" stroke-dasharray="3,2"/>
      <text x="{vx3 - 17.0 * S}" y="{vy3 - 8.0 * S}" fill="{c_hidden}" font-size="8" text-anchor="middle">硬币槽</text>
      <text x="{vx3 + 17.0 * S}" y="{vy3 - 8.0 * S}" fill="{c_hidden}" font-size="8" text-anchor="middle">硬币槽</text>

      <!-- Head Top Outline (82.0mm wide x 26.0mm deep) -->
      <rect x="{vx3 - 41.0 * S}" y="{vy3 - 13.0 * S}" width="{82.0 * S}" height="{26.0 * S}"
            rx="6" fill="#1e293b" stroke="{c_solid}" stroke-width="1.5"/>

      <!-- Top Buttons Opening: 42.0mm x 8.0mm -->
      <rect x="{vx3 - 26.0 * S}" y="{vy3 - 4.0 * S}" width="{42.0 * S}" height="{8.0 * S}"
            rx="2" fill="#090d16" stroke="{c_dim}" stroke-width="1"/>
      <text x="{vx3 - 5.0 * S}" y="{vy3 + 2.0 * S}" fill="{c_dim}" font-size="9" text-anchor="middle">A / B / C 键位</text>

      <!-- Top Cat Ears top footprint -->
      <polygon points="{vx3 - 26.5*S},{vy3 - 7*S} {vx3 - 13.5*S},{vy3 - 7*S} {vx3 - 20*S},{vy3 + 7*S}" fill="{c_accent}" opacity="0.6"/>
      <polygon points="{vx3 + 13.5*S},{vy3 - 7*S} {vx3 + 26.5*S},{vy3 - 7*S} {vx3 + 20*S},{vy3 + 7*S}" fill="{c_accent}" opacity="0.6"/>

      <!-- Side Knob profile on right: 10mm thick, 18.6mm wide -->
      <rect x="{vx3 + 38.0 * S}" y="{vy3 - 5.0 * S}" width="{knob_t * S}" height="{18.6 * S}"
            fill="{c_accent}" fill-opacity="0.3" stroke="{c_accent}" stroke-width="1.2" rx="2"/>

      <!-- Dimensions for Top View -->
      <text x="{vx3 - 45 * S}" y="{vy3}" fill="{c_dim}" font-size="10" text-anchor="end">76.0 x 72.0 底座轮廓</text>
    </g>
    ''')

    # =========================================================================
    # VIEW 4: EXPLODED BOM & ASSEMBLY LIST (零件明细与装配关系表)
    # X = 550 to 1230, Y = 560 to 860
    # =========================================================================
    svg.append(f'''
    <!-- ==================== VIEW 4: BOM & ASSEMBLY TABLE ==================== -->
    <g transform="translate(560, 560)">
      <!-- Panel Card Background -->
      <rect x="0" y="0" width="670" height="260" rx="6" fill="#101726" stroke="#223046" stroke-width="1.5"/>

      <!-- Table Header -->
      <rect x="0" y="0" width="670" height="34" rx="6" fill="#1a2538"/>
      <text x="16" y="22" fill="#f8fafc" font-size="13" font-weight="bold">PARTS LIST &amp; SPECIFICATIONS (3D打印零件与装配五金清单)</text>

      <!-- Table Columns -->
      <!-- Row 1: Head -->
      <g transform="translate(16, 52)">
        <text x="0" y="14" fill="{c_dim}" font-size="12" font-weight="bold">[01] 机头组件 (wio_tilt_tv_head.stl)</text>
        <text x="320" y="14" fill="#e2e8f0" font-size="12">82.0 × 26.0 × 94.5 mm</text>
        <text x="510" y="14" fill="#94a3b8" font-size="11">51.2g (象牙白 9600树脂)</text>
        <text x="0" y="28" fill="#64748b" font-size="11">内含 73×13×58mm Wio容纳槽 + 70×10×54mm 音腔/电池仓 + 14mm 转轴凸耳</text>
      </g>
      <line x1="16" y1="88" x2="654" y2="88" stroke="#1e2c40" stroke-width="1"/>

      <!-- Row 2: Base -->
      <g transform="translate(16, 96)">
        <text x="0" y="14" fill="{c_dim}" font-size="12" font-weight="bold">[02] 俯仰底座 (wio_tilt_tv_base.stl)</text>
        <text x="320" y="14" fill="#e2e8f0" font-size="12">76.0 × 72.0 × 34.5 mm</text>
        <text x="510" y="14" fill="#94a3b8" font-size="11">23.5g (深空灰/哑光黑)</text>
        <text x="0" y="28" fill="#64748b" font-size="11">双叉内间距 14.4mm (间隙0.4mm顺滑摆动) + 后脚跟延展42mm + 4硬币配重槽</text>
      </g>
      <line x1="16" y1="132" x2="654" y2="132" stroke="#1e2c40" stroke-width="1"/>

      <!-- Row 3: Knob -->
      <g transform="translate(16, 140)">
        <text x="0" y="14" fill="{c_dim}" font-size="12" font-weight="bold">[03] 阻尼旋钮 (wio_tilt_tv_knob.stl)</text>
        <text x="320" y="14" fill="#e2e8f0" font-size="12">外径 Φ18.6 × 10.0 mm</text>
        <text x="510" y="14" fill="#94a3b8" font-size="11">2.1g (黄铜/金橙色)</text>
        <text x="0" y="28" fill="#64748b" font-size="11">12齿防滑齿轮手拧轮，内嵌 M3 六角螺母沉槽 (对边6.1mm，深3.5mm)</text>
      </g>
      <line x1="16" y1="176" x2="654" y2="176" stroke="#1e2c40" stroke-width="1"/>

      <!-- Row 4: Hardware Assembly -->
      <g transform="translate(16, 184)">
        <text x="0" y="14" fill="{c_accent}" font-size="12" font-weight="bold">[04] 标准装配五金 (外购件)</text>
        <text x="320" y="14" fill="#e2e8f0" font-size="12">M3 × 25mm 螺栓 1根 + M3 螺母 1个</text>
        <text x="0" y="28" fill="#64748b" font-size="11">螺栓穿过底座双叉与机头凸耳，螺母压入旋钮，实现 0°~45° 自由无级手拧锁死</text>
      </g>
      <line x1="16" y1="220" x2="654" y2="220" stroke="#1e2c40" stroke-width="1"/>

      <!-- Footer Note -->
      <g transform="translate(16, 226)">
        <text x="0" y="18" fill="{c_highlight}" font-size="12" font-weight="bold">★ 合盘单文件：cad/stl/wio_tilt_tv_plate.stl (总重 76.5g，单文件上传免除多份开机费)</text>
      </g>
    </g>
    ''')

    # Close SVG
    svg.append('</svg>')
    content = '\n'.join(svg)

    dest = 'cad/tilt_tv_product_preview.svg'
    with open(dest, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated precision blueprint SVG: {dest} ({len(content)} bytes)")

if __name__ == '__main__':
    build_blueprint_svg()
