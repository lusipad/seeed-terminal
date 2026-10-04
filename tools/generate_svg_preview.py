"""
generate_svg_preview.py - Generates an exquisite vector SVG infographic of the
Wio Terminal Articulated Retro TV Desktop Monitor.
"""

import os

def generate_svg():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 780" width="100%" height="100%" style="background:#0c1017; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;">
  <defs>
    <!-- Gradients -->
    <linearGradient id="bgGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#131b26"/>
      <stop offset="100%" stop-color="#090d14"/>
    </linearGradient>

    <!-- TV Head Plastic Gradient (Ivory White 9600 Resin) -->
    <linearGradient id="tvPlastic" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="50%" stop-color="#f5f2ea"/>
      <stop offset="100%" stop-color="#e3ded2"/>
    </linearGradient>

    <linearGradient id="tvPlasticShadow" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#e3ded2"/>
      <stop offset="100%" stop-color="#cdc5b5"/>
    </linearGradient>

    <!-- CRT Screen Bezel Inset Gradient -->
    <linearGradient id="crtBezel" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2c2823"/>
      <stop offset="50%" stop-color="#1f1c18"/>
      <stop offset="100%" stop-color="#14120f"/>
    </linearGradient>

    <!-- Screen Glass Glow Gradient -->
    <linearGradient id="screenGlass" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>

    <!-- Vintage Brass Knob Gradient -->
    <linearGradient id="brassGold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fde047"/>
      <stop offset="40%" stop-color="#eab308"/>
      <stop offset="100%" stop-color="#ca8a04"/>
    </linearGradient>

    <linearGradient id="brassGoldDark" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ca8a04"/>
      <stop offset="100%" stop-color="#854d0e"/>
    </linearGradient>

    <!-- Base Charcoal Matte Resin -->
    <linearGradient id="basePlastic" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="50%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>

    <!-- Motion Glow -->
    <linearGradient id="cyanGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>

    <!-- Filters -->
    <filter id="dropShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Background Blueprint Canvas -->
  <rect width="1100" height="780" fill="url(#bgGlow)"/>

  <!-- Tech Grid Background -->
  <g opacity="0.07" stroke="#38bdf8" stroke-width="0.8">
    <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
      <path d="M 30 0 L 0 0 0 30"/>
    </pattern>
    <rect width="1100" height="780" fill="url(#grid)"/>
  </g>

  <!-- ========================================================================= -->
  <!-- HEADER & BADGES                                                          -->
  <!-- ========================================================================= -->
  <g transform="translate(60, 48)">
    <rect x="0" y="0" width="136" height="24" rx="12" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="1"/>
    <text x="68" y="16" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle" letter-spacing="1">3D CAD DESIGN</text>
    <text x="0" y="58" fill="#ffffff" font-size="28" font-weight="800" letter-spacing="-0.5">Wio Terminal 可俯仰复古小电视监视器</text>
    <text x="0" y="84" fill="#94a3b8" font-size="14">自由 0° ~ 45° 俯仰调节 • 9600 高韧光敏树脂 • 内嵌共鸣音腔与电池仓 • 免焊接一体机</text>
  </g>

  <!-- ========================================================================= -->
  <!-- MAIN LEFT PANEL: 3D PERSPECTIVE ASSEMBLED HERO VIEW (MAIN PRODUCT)        -->
  <!-- ========================================================================= -->
  <g transform="translate(240, 410)" filter="url(#dropShadow)">

    <!-- Desk Surface Shadow -->
    <ellipse cx="0" cy="180" rx="210" ry="32" fill="#000000" opacity="0.5" filter="url(#softGlow)"/>

    <!-- ==================== DESK BASE (CHARCOAL RESIN) ==================== -->
    <!-- Base Bottom Plate -->
    <path d="M -150 140 L 150 140 L 130 170 L -130 170 Z" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
    <path d="M -150 132 L 150 132 L 150 140 L -150 140 Z" fill="#1e293b"/>
    <!-- Base Top Chamfer Slab -->
    <path d="M -135 120 L 135 120 L 146 132 L -146 132 Z" fill="#334155" stroke="#475569" stroke-width="1.2"/>
    <path d="M -135 120 L 135 120 L 125 108 L -125 108 Z" fill="url(#basePlastic)"/>

    <!-- Dual Upright Support Arms (Clevis) -->
    <!-- Left Arm -->
    <path d="M -32 110 L -18 110 L -18 40 L -32 40 Z" fill="#1e293b"/>
    <circle cx="-25" cy="40" r="14" fill="#334155" stroke="#475569" stroke-width="1.5"/>
    <!-- Right Arm -->
    <path d="M 18 110 L 32 110 L 32 40 L 18 40 Z" fill="#1e293b"/>
    <circle cx="25" cy="40" r="14" fill="#334155" stroke="#475569" stroke-width="1.5"/>

    <!-- Steel Pivot Center Pin -->
    <circle cx="-25" cy="40" r="4.5" fill="#64748b"/>
    <circle cx="25" cy="40" r="4.5" fill="#64748b"/>

    <!-- ==================== BRASS THUMB ADJUSTMENT KNOB ==================== -->
    <g transform="translate(38, 40)">
      <!-- Knurled Teeth Outer Rim -->
      <path d="M 0 -18 L 8 -18 L 10 -14 L 14 -14 L 14 -10 L 18 -8 L 18 0 L 18 8 L 14 10 L 14 14 L 10 14 L 8 18 L 0 18 L -8 18 L -10 14 L -14 14 L -14 10 L -18 8 L -18 0 L -18 -8 L -14 -10 L -14 -14 L -10 -14 L -8 -18 Z" fill="url(#brassGoldDark)" stroke="#ca8a04" stroke-width="1"/>
      <circle cx="0" cy="0" r="13" fill="url(#brassGold)"/>
      <circle cx="0" cy="0" r="7" fill="url(#brassGoldDark)"/>
      <circle cx="0" cy="0" r="3.5" fill="#451a03"/>
      <!-- Indicator Tick -->
      <line x1="0" y1="-12" x2="0" y2="-6" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
    </g>

    <!-- ==================== ROTATING MONITOR HEAD (AT 25° TILT) ==================== -->
    <g transform="rotate(-15, 0, 40)">

      <!-- Bottom Hinge Lug (between clevis arms) -->
      <path d="M -16 35 L 16 35 L 16 5 M -16 5 Z" fill="#d1c9bb" stroke="#b8ad9c" stroke-width="1.2"/>
      <rect x="-16" y="5" width="32" height="30" rx="4" fill="url(#tvPlasticShadow)"/>
      <circle cx="0" cy="40" r="7" fill="#94a3b8"/>

      <!-- ==================== RETRO TV MAIN CABINET ==================== -->
      <!-- Cabinet 3D Depth Extrusion (Right & Top Side Panels) -->
      <path d="M 120 -150 L 152 -130 L 152 10 L 120 -10 Z" fill="#d1c9bb" stroke="#b8ad9c" stroke-width="1.2"/>
      <path d="M -120 -150 L -88 -170 L 152 -130 L 120 -150 Z" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.2"/>

      <!-- Cabinet Front Main Body (Cream/Ivory Resin) -->
      <rect x="-120" y="-150" width="240" height="155" rx="18" fill="url(#tvPlastic)" stroke="#b8ad9c" stroke-width="2"/>

      <!-- Top User Buttons Opening & Wio Terminal ABC Buttons -->
      <rect x="-55" y="-153" width="70" height="6" rx="3" fill="#cbd5e1"/>
      <rect x="-48" y="-156" width="16" height="5" rx="2" fill="#475569"/><text x="-40" y="-158" fill="#94a3b8" font-size="6" text-anchor="middle">A</text>
      <rect x="-26" y="-156" width="16" height="5" rx="2" fill="#475569"/><text x="-18" y="-158" fill="#94a3b8" font-size="6" text-anchor="middle">B</text>
      <rect x="-4" y="-156" width="16" height="5" rx="2" fill="#475569"/><text x="4" y="-158" fill="#94a3b8" font-size="6" text-anchor="middle">C</text>

      <!-- Cute Cat Ears on Top -->
      <!-- Left Ear -->
      <polygon points="-75,-150 -45,-150 -60,-182" fill="url(#tvPlastic)" stroke="#b8ad9c" stroke-width="1.5"/>
      <polygon points="-70,-150 -50,-150 -60,-174" fill="#fbcfe8" opacity="0.8"/>
      <!-- Right Ear -->
      <polygon points="45,-150 75,-150 60,-182" fill="url(#tvPlastic)" stroke="#b8ad9c" stroke-width="1.5"/>
      <polygon points="50,-150 70,-150 60,-174" fill="#fbcfe8" opacity="0.8"/>

      <!-- ==================== FRONT CRT SCREEN BEZEL ==================== -->
      <!-- Curved CRT Tube Bezel Frame -->
      <rect x="-105" y="-138" width="158" height="128" rx="14" fill="url(#crtBezel)" stroke="#453e34" stroke-width="2"/>

      <!-- Screen Inset Border -->
      <rect x="-97" y="-130" width="142" height="112" rx="10" fill="#000000" stroke="#1f2937" stroke-width="1.5"/>

      <!-- Active 2.4" Display (Cozy Pixel Pet / Clock UI) -->
      <rect x="-93" y="-126" width="134" height="104" rx="6" fill="url(#screenGlass)"/>

      <!-- Screen UI Content (Pixel Pet "小维" Room & Clock) -->
      <g transform="translate(-26, -74)">
        <!-- Pixel Wallpaper pattern -->
        <rect x="-65" y="-50" width="130" height="100" fill="#1e1b2e" rx="4"/>
        <!-- Window with Rain/Night -->
        <rect x="-56" y="-42" width="28" height="34" fill="#0f172a" stroke="#3b82f6" stroke-width="1.2" rx="2"/>
        <line x1="-42" y1="-42" x2="-42" y2="-8" stroke="#3b82f6" stroke-width="1"/>
        <line x1="-56" y1="-25" x2="-28" y2="-25" stroke="#3b82f6" stroke-width="1"/>
        <!-- Moon in window -->
        <circle cx="-35" cy="-34" r="3.5" fill="#fde047"/>
        <!-- Cozy Fireplace Hearth -->
        <rect x="26" y="-30" width="30" height="38" fill="#451a03" rx="2"/>
        <polygon points="36,-8 46,-8 41,-22" fill="#f97316"/>
        <polygon points="38,-8 44,-8 41,-18" fill="#fde047"/>

        <!-- Desk Pet "小维" Character (Pixel Cat / Bot) -->
        <g transform="translate(0, 8)">
          <!-- Cat Body -->
          <ellipse cx="0" cy="10" rx="19" ry="14" fill="#ffffff"/>
          <!-- Cat Ears -->
          <polygon points="-14,-2 -5,-2 -10,-14" fill="#ffffff"/>
          <polygon points="-12,-2 -7,-2 -9.5,-10" fill="#f472b6"/>
          <polygon points="5,-2 14,-2 10,-14" fill="#ffffff"/>
          <polygon points="7,-2 12,-2 9.5,-10" fill="#f472b6"/>
          <!-- Cat Head -->
          <circle cx="0" cy="0" r="15" fill="#ffffff"/>
          <!-- Big Anime Cute Blinking Eyes -->
          <ellipse cx="-5" cy="-1" rx="3.5" ry="4.5" fill="#0f172a"/>
          <circle cx="-6" cy="-2.5" r="1.5" fill="#ffffff"/>
          <ellipse cx="5" cy="-1" rx="3.5" ry="4.5" fill="#0f172a"/>
          <circle cx="4" cy="-2.5" r="1.5" fill="#ffffff"/>
          <!-- Rosy Cheeks -->
          <circle cx="-9" cy="4" r="2.2" fill="#fb7185" opacity="0.6"/>
          <circle cx="9" cy="4" r="2.2" fill="#fb7185" opacity="0.6"/>
          <!-- Cat Mouth -->
          <path d="M -3 3 Q 0 5 3 3" fill="none" stroke="#0f172a" stroke-width="1.2" stroke-linecap="round"/>
        </g>

        <!-- Big 75px Digital Cyber Clock overlay on top -->
        <rect x="-56" y="24" width="112" height="20" rx="4" fill="#000000" opacity="0.65"/>
        <text x="0" y="38" fill="#38bdf8" font-size="12" font-weight="900" font-family="monospace" text-anchor="middle" letter-spacing="1">14:28:56</text>
      </g>

      <!-- Glass Glare Reflection -->
      <path d="M -90 -124 L -40 -124 L -90 -40 Z" fill="#ffffff" opacity="0.08"/>

      <!-- ==================== RIGHT VINTAGE CONTROL PANEL ==================== -->
      <!-- Panel Divider Groove -->
      <line x1="62" y1="-140" x2="62" y2="-5" stroke="#d1c9bb" stroke-width="1.5"/>

      <!-- Upper Vintage Rotary Knob -->
      <g transform="translate(88, -112)">
        <circle cx="0" cy="0" r="15" fill="#d8d1c2" stroke="#b8ad9c" stroke-width="1"/>
        <circle cx="0" cy="0" r="11" fill="url(#brassGold)" stroke="#ca8a04" stroke-width="1"/>
        <circle cx="0" cy="0" r="5" fill="url(#brassGoldDark)"/>
        <line x1="0" y1="-10" x2="0" y2="-4" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
        <!-- Notch marks around knob -->
        <circle cx="-16" cy="0" r="1" fill="#78716c"/>
        <circle cx="16" cy="0" r="1" fill="#78716c"/>
        <circle cx="0" cy="-16" r="1" fill="#78716c"/>
        <circle cx="0" cy="16" r="1" fill="#78716c"/>
      </g>

      <!-- Lower Vintage Rotary Knob -->
      <g transform="translate(88, -68)">
        <circle cx="0" cy="0" r="15" fill="#d8d1c2" stroke="#b8ad9c" stroke-width="1"/>
        <circle cx="0" cy="0" r="11" fill="url(#brassGold)" stroke="#ca8a04" stroke-width="1"/>
        <circle cx="0" cy="0" r="5" fill="url(#brassGoldDark)"/>
        <line x1="7" y1="-7" x2="3" y2="-3" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
      </g>

      <!-- 5-Way Joystick Cutout & Wio Joystick -->
      <g transform="translate(88, -26)">
        <circle cx="0" cy="0" r="12" fill="#2c2823" stroke="#453e34" stroke-width="1.2"/>
        <!-- Blue Joystick Cross Cap -->
        <circle cx="0" cy="0" r="6" fill="#0284c7" stroke="#38bdf8" stroke-width="1.2"/>
        <path d="M 0 -4 L 0 4 M -4 0 L 4 0" stroke="#ffffff" stroke-width="1.5"/>
      </g>

      <!-- Speaker Acoustic Slits below screen -->
      <line x1="-90" y1="-4" x2="-40" y2="-4" stroke="#8c8273" stroke-width="2" stroke-linecap="round"/>
      <line x1="-30" y1="-4" x2="20" y2="-4" stroke="#8c8273" stroke-width="2" stroke-linecap="round"/>

    </g> <!-- End Rotating Monitor Head -->

    <!-- ==================== TILT ANGLE MOTION ARC & LABELS ==================== -->
    <g transform="translate(-140, 20)">
      <path d="M 0 20 A 70 70 0 0 1 35 -35" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="4,3"/>
      <polygon points="37,-38 41,-28 30,-32" fill="#38bdf8"/>
      <!-- Angle Markers -->
      <text x="-15" y="24" fill="#94a3b8" font-size="11" font-family="monospace">0°</text>
      <text x="45" y="-36" fill="#38bdf8" font-size="12" font-weight="bold" font-family="monospace">45° 仰视</text>
      <text x="18" y="-4" fill="#38bdf8" font-size="10" font-weight="bold">自由俯仰摆动</text>
    </g>

  </g> <!-- End Main Left Panel -->

  <!-- ========================================================================= -->
  <!-- RIGHT TOP PANEL: SIDE PROFILE TILT RANGE (0° ~ 45°)                       -->
  <!-- ========================================================================= -->
  <g transform="translate(680, 80)">
    <!-- Panel Background Card -->
    <rect x="0" y="0" width="370" height="290" rx="14" fill="#131b26" stroke="#232f3e" stroke-width="1.5"/>
    <text x="24" y="36" fill="#ffffff" font-size="16" font-weight="bold">📐 侧面无级俯仰机构原理</text>
    <text x="24" y="56" fill="#94a3b8" font-size="12">阻尼铰链 + 复古齿轮手拧锁紧旋钮</text>

    <!-- Side Diagram Schematic -->
    <g transform="translate(80, 190)">
      <!-- Base in side view -->
      <path d="M -50 45 L 90 45 L 80 55 L -45 55 Z" fill="#334155"/>
      <rect x="15" y="5" width="16" height="40" rx="4" fill="#1e293b"/>
      <circle cx="23" cy="15" r="9" fill="#475569"/>

      <!-- Position 1: 0° Vertical (Dashed line) -->
      <g opacity="0.35">
        <rect x="15" y="-105" width="16" height="120" rx="6" fill="#cbd5e1" stroke="#94a3b8" stroke-width="1"/>
        <text x="4" y="-85" fill="#cbd5e1" font-size="10" font-family="monospace">0° 垂直</text>
      </g>

      <!-- Position 2: 25° Optimal Desktop (Active) -->
      <g transform="rotate(25, 23, 15)">
        <rect x="15" y="-105" width="22" height="120" rx="6" fill="url(#tvPlastic)" stroke="#b8ad9c" stroke-width="1.5"/>
        <!-- Screen side line -->
        <line x1="15" y1="-95" x2="15" y2="-10" stroke="#38bdf8" stroke-width="3"/>
        <polygon points="12,-105 22,-105 17,-120" fill="url(#tvPlastic)"/>
      </g>

      <!-- Position 3: 45° Max Tilt (Dashed line) -->
      <g transform="rotate(45, 23, 15)" opacity="0.35">
        <rect x="15" y="-105" width="16" height="120" rx="6" fill="#cbd5e1" stroke="#94a3b8" stroke-width="1"/>
        <text x="25" y="-110" fill="#cbd5e1" font-size="10" font-family="monospace">45°</text>
      </g>

      <!-- Pivot Center & Knurled Knob -->
      <circle cx="23" cy="15" r="11" fill="url(#brassGold)" stroke="#ca8a04" stroke-width="1"/>
      <circle cx="23" cy="15" r="4" fill="#713f12"/>

      <!-- Tilt Travel Arc -->
      <path d="M 23 -85 A 100 100 0 0 1 85 -55" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="3,3"/>
      <polygon points="87,-54 82,-62 78,-52" fill="#38bdf8"/>
    </g>

    <!-- Legend & Feature List -->
    <g transform="translate(200, 95)" font-size="12">
      <circle cx="0" cy="8" r="4" fill="#38bdf8"/>
      <text x="14" y="12" fill="#e2e8f0" font-weight="bold">0° 垂直角度</text>
      <text x="14" y="28" fill="#94a3b8" font-size="11">适合站姿办公或远距离看板</text>

      <circle cx="0" cy="50" r="4" fill="#fde047"/>
      <text x="14" y="54" fill="#e2e8f0" font-weight="bold">25° ~ 30° 黄金视距</text>
      <text x="14" y="70" fill="#94a3b8" font-size="11">桌面坐姿正常对视，最舒服</text>

      <circle cx="0" cy="92" r="4" fill="#38bdf8"/>
      <text x="14" y="96" fill="#e2e8f0" font-weight="bold">45° 大仰视角度</text>
      <text x="14" y="112" fill="#94a3b8" font-size="11">低矮茶几或站立低头视察</text>

      <rect x="0" y="132" width="150" height="26" rx="6" fill="#38bdf8" fill-opacity="0.1" stroke="#38bdf8" stroke-width="1"/>
      <text x="75" y="149" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">🤏 随手一拧即锁死</text>
    </g>
  </g>

  <!-- ========================================================================= -->
  <!-- RIGHT BOTTOM PANEL: INTERNAL HARDWARE ARCHITECTURE (CUTAWAY)              -->
  <!-- ========================================================================= -->
  <g transform="translate(680, 395)">
    <!-- Panel Background Card -->
    <rect x="0" y="0" width="370" height="340" rx="14" fill="#131b26" stroke="#232f3e" stroke-width="1.5"/>
    <text x="24" y="36" fill="#ffffff" font-size="16" font-weight="bold">🎛️ 内部音腔与免焊接硬件布局</text>
    <text x="24" y="56" fill="#94a3b8" font-size="12">大容量背部隐藏腔室，0 焊锡杜邦线插拔</text>

    <!-- Cutaway Exploded Architecture Graphic -->
    <g transform="translate(24, 75)">

      <!-- Component 1: Wio Terminal Main Unit -->
      <rect x="0" y="0" width="322" height="42" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>
      <rect x="10" y="8" width="26" height="26" rx="4" fill="#0284c7"/>
      <text x="23" y="25" fill="#ffffff" font-size="10" font-weight="bold" text-anchor="middle">WIO</text>
      <text x="46" y="20" fill="#f8fafc" font-size="13" font-weight="bold">Wio Terminal 2.4" 主机</text>
      <text x="46" y="34" fill="#94a3b8" font-size="11">原厂屏幕 + SAMD51 + 摇杆直接自前框嵌入</text>

      <!-- Component 2: MAX98357A I2S DAC Amp -->
      <g transform="translate(0, 52)">
        <rect x="0" y="0" width="322" height="42" rx="8" fill="#1e293b" stroke="#ca8a04" stroke-width="1.2"/>
        <rect x="10" y="8" width="26" height="26" rx="4" fill="#ca8a04"/>
        <text x="23" y="25" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">AMP</text>
        <text x="46" y="20" fill="#f8fafc" font-size="13" font-weight="bold">MAX98357A I2S 功放模块</text>
        <text x="46" y="34" fill="#94a3b8" font-size="11">5 根杜邦线对插 40-Pin，高保真数字解码发声</text>
      </g>

      <!-- Component 3: 8Ω 2W Cavity Speaker -->
      <g transform="translate(0, 104)">
        <rect x="0" y="0" width="322" height="42" rx="8" fill="#1e293b" stroke="#ec4899" stroke-width="1.2"/>
        <rect x="10" y="8" width="26" height="26" rx="4" fill="#ec4899"/>
        <text x="23" y="25" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">SPK</text>
        <text x="46" y="20" fill="#f8fafc" font-size="13" font-weight="bold">8Ω 2W 独立共鸣腔小喇叭</text>
        <text x="46" y="34" fill="#94a3b8" font-size="11">对准背板百叶窗出音孔，人声洪亮通透</text>
      </g>

      <!-- Component 4: 1000mAh Battery (Optional) -->
      <g transform="translate(0, 156)">
        <rect x="0" y="0" width="322" height="42" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1.2"/>
        <rect x="10" y="8" width="26" height="26" rx="4" fill="#10b981"/>
        <text x="23" y="25" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">BAT</text>
        <text x="46" y="20" fill="#f8fafc" font-size="13" font-weight="bold">1000mAh 超薄聚合物锂电池</text>
        <text x="46" y="34" fill="#94a3b8" font-size="11">可选装 603040 电池，摆脱线缆束缚随手拿</text>
      </g>

      <!-- Summary Pill -->
      <g transform="translate(0, 210)">
        <rect x="0" y="0" width="322" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
        <text x="161" y="22" fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">🔥 全套配件成本约 15~20 元，淘宝直接配齐</text>
      </g>

    </g>
  </g>

  <!-- ========================================================================= -->
  <!-- BOTTOM STATUS FOOTER BAR                                                  -->
  <!-- ========================================================================= -->
  <g transform="translate(60, 715)">
    <rect x="0" y="0" width="580" height="38" rx="8" fill="#131b26" stroke="#232f3e" stroke-width="1"/>
    <text x="24" y="24" fill="#94a3b8" font-size="12">
      <tspan font-weight="bold" fill="#ffffff">整机规格：</tspan> 82 × 96 × 68 mm  |  
      <tspan font-weight="bold" fill="#ffffff">整套克重：</tspan> 约 75g (合盘一锅出)  |  
      <tspan font-weight="bold" fill="#ffffff">材质：</tspan> 9600 高韧白树脂
    </text>
  </g>

</svg>'''

    dest = 'cad/tilt_tv_product_preview.svg'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"Generated SVG: {dest} ({len(svg)} bytes)")

if __name__ == '__main__':
    generate_svg()
