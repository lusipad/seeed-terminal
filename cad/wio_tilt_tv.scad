// ==============================================================================
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
