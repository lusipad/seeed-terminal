// ==============================================================================
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
