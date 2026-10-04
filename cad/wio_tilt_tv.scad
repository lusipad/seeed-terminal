// Wio Terminal 可俯仰摆动复古小电视监视器 (OpenSCAD 源码)
// 支持 0° ~ 45° 自由俯仰调节
$fn = 60;
mode = "assembly"; // "assembly", "head", "base", "knob"
tilt_deg = 25;

module tv_head() {
    difference() {
        union() {
            translate([-42, 0, 0]) cube([84, 30, 66]);
            // 转轴凸耳 (宽 14mm)
            translate([-7, 7, -14]) cube([14, 16, 14]);
            translate([0, 15, -7]) rotate([0, 90, 0]) cylinder(r=8, h=14, center=true);
            // 旋钮
            translate([28, -2, 45]) rotate([-90,0,0]) cylinder(r=5.5, h=3.5);
            translate([28, -2, 23]) rotate([-90,0,0]) cylinder(r=5.5, h=3.5);
        }
        // 屏幕视窗 (50x38mm)
        translate([-6, -2, 33 - 19]) cube([50, 6, 38]);
        // Wio Terminal 槽 (73x13x58mm)
        translate([-36.5, 3, 33 - 29]) cube([73, 13, 58]);
        // 音腔/电池仓 (64x14x48mm)
        translate([-32, 15, 33 - 24]) cube([64, 14, 48]);
        // 转轴过孔 (M3)
        translate([0, 15, -7]) rotate([0, 90, 0]) cylinder(d=3.6, h=30, center=true);
        // Type-C 槽
        translate([-43, 4, 27]) cube([6, 16, 12]);
    }
}

module tv_base() {
    difference() {
        union() {
            translate([-39, 0, 0]) cube([78, 68, 5]);
            // 双叉支架 (内间距 14.8mm)
            translate([-13.0, 25, 5]) cube([5.6, 18, 24]);
            translate([  7.4, 25, 5]) cube([5.6, 18, 24]);
            translate([-10.2, 34, 29]) rotate([0, 90, 0]) cylinder(r=9, h=5.6, center=true);
            translate([ 10.2, 34, 29]) rotate([0, 90, 0]) cylinder(r=9, h=5.6, center=true);
        }
        // 转轴通孔
        translate([0, 34, 29]) rotate([0, 90, 0]) cylinder(d=3.6, h=50, center=true);
    }
}

module thumb_knob() {
    difference() {
        cylinder(r=9, h=7);
        translate([0, 0, -1]) cylinder(d=3.4, h=12);
        translate([0, 0, -1]) cylinder(r=3.5, h=3.5, $fn=6);
    }
}

if (mode == "assembly") {
    color("#444444") tv_base();
    translate([0, 34, 29]) rotate([tilt_deg, 0, 0]) translate([0, -15, 7]) color("#F5F2EB") tv_head();
    translate([14, 34, 29]) rotate([0, 90, 0]) color("#C8A165") thumb_knob();
} else if (mode == "head") tv_head();
else if (mode == "base") tv_base();
else if (mode == "knob") thumb_knob();
