// M3 printed-post coupon for the improved1 enclosure.
// Print this before the full shell and test the exact screw/material/profile.
$fn = 72;

base_t = 3.0;
post_od = 10.0;
post_h = 12.0;
pilot_diameters = [2.5, 2.7, 2.9];
pitch = 18.0;
edge = 8.0;

difference() {
  union() {
    cube([edge*2 + pitch*(len(pilot_diameters)-1), 22, base_t]);
    for (i = [0:len(pilot_diameters)-1])
      translate([edge + i*pitch, 11, base_t - 0.2])
        cylinder(d=post_od, h=post_h + 0.2);
  }
  for (i = [0:len(pilot_diameters)-1])
    translate([edge + i*pitch, 11, base_t])
      cylinder(d=pilot_diameters[i], h=post_h + 0.5);
}
