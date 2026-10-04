// ==============================================================================
// Wio Terminal 桌面多功能 30° 仰角底座与音腔背壳 (Desktop Angled Dock & Sound Chamber)
// ==============================================================================
$fn = 60;
wio_width   = 72.0;
wio_height  = 57.0;
wio_depth   = 12.0;
dock_width  = 84.0;
dock_depth  = 74.0;
front_h     = 10.0;
back_h      = 46.0;
tilt_angle  = 30.0;

module wio_desktop_dock() {
    difference() {
        union() {
            translate([-dock_width/2, 0, 0]) cube([dock_width, dock_depth, 3.0]);
            translate([-dock_width/2, 0, 0]) cube([dock_width, 4.0, 14.0]);
            translate([-dock_width/2 + 4.5, dock_depth - 3.5, 0]) cube([dock_width - 9.0, 3.5, back_h]);
            rotate([tilt_angle, 0, 0])
                translate([-dock_width/2 + 4.5, 10.0, -2.0]) cube([dock_width - 9.0, 60.0, 3.5]);
            translate([-20 - 4, dock_depth/2 - 4, 12]) cube([8, 8, 12]);
            translate([ 20 - 4, dock_depth/2 - 4, 12]) cube([8, 8, 12]);
        }
        translate([-30, 15, 3.0]) cube([60, 45, 18]);
        for (i = [-5 : 5]) {
            translate([i * 6.5 - 1.2, dock_depth - 5.0, 14.0]) cube([2.4, 8.0, 22.0]);
        }
        translate([-dock_width/2 - 1, 14.0, 4.0]) cube([10.0, 18.0, 10.0]);
    }
}
wio_desktop_dock();
