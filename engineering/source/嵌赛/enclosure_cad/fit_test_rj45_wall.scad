// ============================================================================
//  fit_test_rj45_wall.scad — RJ45 interface cutout test plate (enclosure-prep2)
//  Purpose: verify the RJ45 cutout size + corner radius and confirm the hole
//  pierces a wall_thickness-thick wall, before cutting the full enclosure.
//  Sizes are PLACEHOLDER — 待实测 (to-be-measured).
//
//  Values MUST be kept in sync with the matching parameter block at the top of
//  rough_enclosure_v1.scad (interfaces[0]).
//
//  Prints flat, no supports: a flat plate with the hole cut through its
//  2.4 mm thickness. Check an actual RJ45 jack/plug passes through freely.
// ============================================================================

$fn = 72;

// ---- keep in sync with rough_enclosure_v1.scad ----
wall_thickness = 2.4;
cutout_w = 16;   // RJ45 opening width  [placeholder, 待实测]
cutout_h = 14;   // RJ45 opening height [placeholder, 待实测]
cutout_r = 2;    // corner radius       [placeholder, 待实测]
// ------------------------------------------------
margin = 12;     // border around the cutout

plate_w = cutout_w + 2*margin;
plate_h = cutout_h + 2*margin;

module rounded_rect_2d(w, h, r) {
  if (r > 0) {
    offset(r = r) square([w - 2*r, h - 2*r], center = true);
  } else {
    square([w, h], center = true);
  }
}

difference() {
  cube([plate_w, plate_h, wall_thickness]);
  translate([plate_w/2, plate_h/2, -1])
    linear_extrude(height = wall_thickness + 2)
      rounded_rect_2d(cutout_w, cutout_h, cutout_r);
}
