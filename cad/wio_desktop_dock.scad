// ==============================================================================
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
