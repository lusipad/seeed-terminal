// Wio Terminal 30° 桌面固定底座与音腔背壳 (OpenSCAD 源码)
// 官方标准两 M3 螺丝孔距: 61.00 mm (X = +/- 30.5 mm)
$fn = 60;
module wio_dock() {
    difference() {
        union() {
            translate([-42, 0, 0]) cube([84, 74, 3]);
            translate([-42, 0, 0]) cube([84, 4, 14]);
            translate([-42, 70, 0]) cube([84, 4, 46]);
            rotate([28, 0, 0]) translate([-42, 10, 0]) cube([84, 62, 4]);
            // 螺丝固定座 (X = +/- 30.5mm)
            translate([-30.5 - 4, 30, 0]) cube([8, 12, 18]);
            translate([ 30.5 - 4, 30, 0]) cube([8, 12, 18]);
        }
        // 内部空腔
        translate([-27, 16, 2]) cube([54, 44, 20]);
        // M3 穿孔 (间距 61.00mm)
        translate([-30.5, 36, 0]) cylinder(d=3.4, h=40);
        translate([ 30.5, 36, 0]) cylinder(d=3.4, h=40);
        // Type-C 出线口
        translate([-43, 12, 2]) cube([6, 18, 12]);
    }
}
wio_dock();
