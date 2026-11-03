// ============================================================================
//  rough_enclosure_v1.scad  —  ROUGH parameterized desktop enclosure
//  (base "下壳" + lid "上盖") for a Linux/FPGA main board + an RX Pluto SDR.
//
//  STATUS: ROUGH FIRST VERSION ONLY.
//  All default dimensions are PLACEHOLDER values, NOT measured. Every interface
//  cutout and every device size/position is 待实测 (to-be-measured). Do NOT use
//  these numbers for a print-fit part. This file only establishes a
//  parameterized structure and spatial layout.
//
//  Coordinate convention (all units mm):
//    X = length (0 .. case_length),  Y = width (0 .. case_width),  Z = up
//    faces: "front" = y=0, "back" = y=case_width, "left" = x=0, "right" = x=case_length
//
//  Red lines honored here:
//    - No snap clips (fragile on unverified dimensions). Lid is held by 4 corner M3 screws.
//    - Device placeholders are preview-only and are NOT part of base/lid/assembly geometry.
//    - The .scad source is the master; STLs are always exported from it.
// ============================================================================

$fn = 72;   // facet resolution for cylinders / arcs / spheres

// ----------------------------------------------------------------------------
// MODE SELECTOR (single value)
//   "assembly"  : base + lid placed together (placeholders shown as ghost, NOT exported)
//   "base"      : base shell only (下壳)
//   "lid"       : lid only, print-friendly orientation (上盖)
//   "preview"   : see-through shell + solid device placeholders + interface labels
// ----------------------------------------------------------------------------
part = "assembly";

// ----------------------------------------------------------------------------
// 1. CASE PARAMETERS  (edit these; everything else derives from them)
// ----------------------------------------------------------------------------
case_length     = 220;   // outer length (X)                     [placeholder, 待实测]
case_width      = 160;   // outer width  (Y)                     [placeholder, 待实测]
case_height     = 70;    // TOTAL assembled height (base + lid)  [placeholder, 待实测]
wall_thickness    = 2.4;  // vertical wall thickness (keep >= 2.0 for structure)
base_thickness    = 3.0;  // base floor thickness
lid_thickness     = 2.4;  // lid top-plate thickness
corner_radius     = 8;    // outer corner radius
fit_clearance     = 0.35; // gap between lid lip and base inner wall (per side)
lid_lip_height    = 4;    // lid locating-lip drop (into the base)
lid_lip_thickness = 1.6;  // lid locating-lip wall thickness
feature_overlap    = 0.20; // fuse studs/posts/ribs into the floor; avoids coplanar-only unions

// Printer-envelope audit only (does not change geometry).
printer_bed_length = 220;  // placeholder: replace with the actual usable bed size
printer_bed_width  = 220;
printer_edge_margin = 5;

// ---- derived (do not edit directly) ----
base_height      = case_height - lid_thickness;               // base shell height; lid plate sits on the rim
inner_radius     = corner_radius - wall_thickness;            // base cavity corner radius
lip_outer_radius = corner_radius - wall_thickness - fit_clearance; // lid lip outer corner radius
lip_inner_radius = lip_outer_radius - lid_lip_thickness;      // lid lip inner corner radius
lip_outer_len    = case_length - 2*wall_thickness - 2*fit_clearance; // lid lip outer footprint
lip_outer_wid    = case_width  - 2*wall_thickness - 2*fit_clearance;
lip_inner_len    = lip_outer_len - 2*lid_lip_thickness;
lip_inner_wid    = lip_outer_wid - 2*lid_lip_thickness;

// ----------------------------------------------------------------------------
// 2. MOUNTING STUDS (M3, for the main board) — edit the ARRAY to move studs
// ----------------------------------------------------------------------------
stud_od      = 7;      // stud outer diameter
stud_height  = 6;      // stud height above the base floor
stud_pilot_d = 2.7;    // provisional M3 self-tap pilot; validate with a printed coupon
board_mounts = [[27,57],[137,57],[27,133],[137,133]];   // [x,y] pairs — 待实测

// ----------------------------------------------------------------------------
// 3. CORNER SCREW POSTS (lid fastening, M3) + matching lid through-holes
// ----------------------------------------------------------------------------
corner_post_od         = 10;   // tall post diameter; increased from 7 for stiffness
corner_post_pilot_d    = 2.7;  // provisional M3 self-tap pilot in the plastic post
lid_screw_clearance_d  = 3.4;  // independent M3 clearance hole through the lid
corner_post_hole_depth = 12;   // blind hole depth from the rim
corner_post_inset      = 12;   // post centre inset from the outer corner (X and Y)
corner_post_rib_t      = 2.4;  // two wall-connecting ribs per post
corner_posts = [
  [corner_post_inset, corner_post_inset],
  [case_length - corner_post_inset, corner_post_inset],
  [corner_post_inset, case_width - corner_post_inset],
  [case_length - corner_post_inset, case_width - corner_post_inset]
];

// ----------------------------------------------------------------------------
// 4. INTERFACE CUTOUTS — unified parameter-array driven (no per-cutout code)
//    field order: [face, hpos, vpos, w_or_d, h, r_or_type, "label"]
//      face   : "front" | "back" | "left" | "right"
//      hpos   : position along the face horizontal axis (mm)
//      vpos   : position above the base floor (mm)
//      w_or_d : rectangle width, or hole DIAMETER when h <= 0 (round hole)
//      h      : rectangle height; set 0 for a round hole
//      r_or_type: rectangle corner radius (0 = sharp) — ignored for round holes
//      label  : human-readable name
//    ALL SIZES AND POSITIONS ARE PLACEHOLDER — 待实测.
// ----------------------------------------------------------------------------
interfaces = [
  ["back",  70, 30, 16, 14, 2, "RJ45 Ethernet 待实测"],
  ["back", 110, 28, 13, 15, 2, "USB 待实测"],
  ["back", 150, 26,  9, 12, 2, "serial 待实测"],
  ["back", 190, 22,  8, 10, 2, "power 待实测"],
  ["right", 40, 40, 6.5, 0, "round", "SMA-1 待实测"],
  ["right", 80, 40, 6.5, 0, "round", "SMA-2 待实测"],
  ["left",  60, 35, 20, 15, 2, "spare-1 待实测"],
  ["left", 120, 35, 20, 15, 2, "spare-2 待实测"]
];

// ----------------------------------------------------------------------------
// 5. VENTILATION (passive)
// ----------------------------------------------------------------------------
vent_hole_d   = 3.0;             // lid vent hole diameter
vent_spacing  = 7.0;             // lid vent grid pitch
vent_cols     = 12;              // lid vent columns
vent_rows     = 6;               // lid vent rows
vent_cx       = case_length / 2; // lid vent matrix centre X
vent_cy       = case_width  / 2; // lid vent matrix centre Y

side_vent_face    = "right";  // intake side ("left" or "right")
side_vent_d       = 3.5;
side_vent_spacing = 8;
side_vent_cols    = 3;
side_vent_rows    = 2;
side_vent_hpos    = 130;      // centre along the side face horizontal axis
side_vent_vpos    = 16;       // centre above the base floor

// ---- fan placeholder (reserved; NOT cut by default) ----
enable_fan_cutout = false;
fan_size          = 40;       // nominal fan size (40 = 40 mm fan)

// ----------------------------------------------------------------------------
// 6. DEVICE PLACEHOLDERS — visual / interference check ONLY, never exported.
//    field order: [label, length, width, height, pos_x, pos_y, pos_z, rot_z, color]
//      pos_x / pos_y = block CENTRE in X/Y;  pos_z = BOTTOM face height (mm);
//      rot_z = rotation about Z (degrees, CCW).
//    ALL SIZES AND POSITIONS ARE PLACEHOLDER — 待实测.
// ----------------------------------------------------------------------------
placeholders = [
  ["main-board", 130, 95, 20,  82, 95, base_thickness + stud_height, 0, "limegreen"],
  ["pluto-sdr",   70, 45, 20, 183, 33, base_thickness,               0, "dodgerblue"],
  ["cable-bend",  40, 30, 30, 190, 95, base_thickness,               0, "orange"]
];


// ============================================================================
//  PARAMETER AUDIT — fail early for impossible geometry; warn for placeholders
// ============================================================================
assert(case_length > 2*(wall_thickness + corner_radius), "case_length too small");
assert(case_width > 2*(wall_thickness + corner_radius), "case_width too small");
assert(base_height > base_thickness + lid_lip_height, "case height leaves no usable cavity");
assert(wall_thickness >= 2.0, "wall_thickness must stay >= 2.0 mm");
assert(base_thickness >= 2.4, "base_thickness must stay >= 2.4 mm");
assert(inner_radius > 0 && lip_outer_radius > 0 && lip_inner_radius > 0,
       "corner/lip radii became non-positive");
assert(fit_clearance > 0, "lid fit clearance must be positive");
assert(stud_pilot_d > 0 && stud_pilot_d < stud_od, "invalid board-stud pilot diameter");
assert(corner_post_pilot_d > 0 && corner_post_pilot_d < corner_post_od,
       "invalid corner-post pilot diameter");
assert(lid_screw_clearance_d >= 3.2, "lid M3 clearance hole is too small");

if (case_length + 2*printer_edge_margin > printer_bed_length ||
    case_width + 2*printer_edge_margin > printer_bed_width)
  echo(str("WARNING_PRINT_BED_MARGIN case=", case_length, "x", case_width,
           " margin=", printer_edge_margin, " bed=", printer_bed_length,
           "x", printer_bed_width));

for (m = board_mounts)
  assert(m[0] > wall_thickness + stud_od/2 &&
         m[0] < case_length - wall_thickness - stud_od/2 &&
         m[1] > wall_thickness + stud_od/2 &&
         m[1] < case_width - wall_thickness - stud_od/2,
         str("board mount outside cavity: ", m));

for (p = placeholders)
  if (p[7] == 0 &&
      (p[4] - p[1]/2 < wall_thickness ||
       p[4] + p[1]/2 > case_length - wall_thickness ||
       p[5] - p[2]/2 < wall_thickness ||
       p[5] + p[2]/2 > case_width - wall_thickness))
    echo(str("WARNING_PLACEHOLDER_INTERSECTS_WALL label=", p[0]));


// ============================================================================
//  GEOMETRY HELPERS
// ============================================================================

// 2D rounded rectangle, centred at the origin in the X-Y plane
module rounded_rect_2d(w, h, r) {
  if (r > 0) {
    offset(r = r) square([w - 2*r, h - 2*r], center = true);
  } else {
    square([w, h], center = true);
  }
}

// rounded-rectangle prism extruded along Z, centred at (cx, cy), from z0 up by t
module rounded_rect_prism(cx, cy, z0, w, h, r, t) {
  translate([cx, cy, z0])
    linear_extrude(height = t)
      rounded_rect_2d(w, h, r);
}

// round hole through a vertical wall (axis along the face normal)
module round_hole(face, hpos, vpos, d) {
  if (face == "front") {
    translate([hpos, 0, vpos]) rotate([90, 0, 0])
      cylinder(d = d, h = wall_thickness * 3, center = true);
  } else if (face == "back") {
    translate([hpos, case_width, vpos]) rotate([90, 0, 0])
      cylinder(d = d, h = wall_thickness * 3, center = true);
  } else if (face == "left") {
    translate([0, hpos, vpos]) rotate([0, 90, 0])
      cylinder(d = d, h = wall_thickness * 3, center = true);
  } else if (face == "right") {
    translate([case_length, hpos, vpos]) rotate([0, 90, 0])
      cylinder(d = d, h = wall_thickness * 3, center = true);
  }
}

// rounded rectangular hole through a vertical wall
module rect_hole(face, hpos, vpos, w, h, r) {
  if (face == "front" || face == "back") {
    ypos = (face == "front") ? 0 : case_width;
    translate([hpos, ypos, vpos]) rotate([90, 0, 0])
      linear_extrude(height = wall_thickness * 3, center = true)
        rounded_rect_2d(w, h, r);
  } else if (face == "left" || face == "right") {
    xpos = (face == "left") ? 0 : case_length;
    translate([xpos, hpos, vpos]) rotate([0, 90, 0]) rotate([0, 0, 90])
      linear_extrude(height = wall_thickness * 3, center = true)
        rounded_rect_2d(w, h, r);
  }
}

// interface cutout dispatch (round when h <= 0, else rounded rectangle)
module cutout(c) {
  if (c[4] <= 0) {
    round_hole(c[0], c[1], c[2], c[3]);
  } else {
    rect_hole(c[0], c[1], c[2], c[3], c[4], c[5]);
  }
}

// side intake vents (round holes on one side wall)
module side_vents() {
  for (i = [0 : side_vent_cols - 1], j = [0 : side_vent_rows - 1]) {
    hx = side_vent_hpos + (i - (side_vent_cols - 1) / 2) * side_vent_spacing;
    vz = side_vent_vpos + (j - (side_vent_rows - 1) / 2) * side_vent_spacing;
    round_hole(side_vent_face, hx, vz, side_vent_d);
  }
}


// ============================================================================
//  BASE (下壳)
// ============================================================================

// M3 board-mounting stud on the base floor
module board_stud(x, y) {
  difference() {
    translate([x, y, base_thickness - feature_overlap])
      cylinder(d = stud_od, h = stud_height + feature_overlap);
    translate([x, y, base_thickness])
      cylinder(d = stud_pilot_d, h = stud_height + 0.002);
  }
}

module corner_post_ribs(c) {
  rib_h = base_height - base_thickness - lid_lip_height - 0.5;
  // Extend slightly into the wall so CGAL sees a true volumetric union rather
  // than a coplanar contact (which can emit zero-area STL triangles).
  wall_x = c[0] < case_length/2
         ? wall_thickness - feature_overlap
         : case_length - wall_thickness + feature_overlap;
  wall_y = c[1] < case_width/2
         ? wall_thickness - feature_overlap
         : case_width - wall_thickness + feature_overlap;
  translate([min(c[0], wall_x), c[1] - corner_post_rib_t/2,
             base_thickness - feature_overlap])
    cube([abs(c[0] - wall_x), corner_post_rib_t, rib_h + feature_overlap]);
  translate([c[0] - corner_post_rib_t/2, min(c[1], wall_y),
             base_thickness - feature_overlap])
    cube([corner_post_rib_t, abs(c[1] - wall_y), rib_h + feature_overlap]);
}

// corner screw posts (full-height, blind M3 pilot from the rim)
module corner_screw_posts() {
  for (c = corner_posts) {
    corner_post_ribs(c);
    difference() {
      translate([c[0], c[1], base_thickness - feature_overlap])
        cylinder(d = corner_post_od, h = base_height - base_thickness + feature_overlap);
      translate([c[0], c[1], base_height - corner_post_hole_depth - 0.001])
        cylinder(d = corner_post_pilot_d, h = corner_post_hole_depth + 0.002);
    }
  }
}

module base_shell() {
  difference() {
    // outer shell
    rounded_rect_prism(case_length/2, case_width/2, 0,
                       case_length, case_width, corner_radius, base_height);
    // inner cavity (opens through the top rim)
    rounded_rect_prism(case_length/2, case_width/2, base_thickness,
                       case_length - 2*wall_thickness,
                       case_width  - 2*wall_thickness,
                       max(0.5, inner_radius),
                       base_height - base_thickness + 1);
    // interface cutouts
    for (c = interfaces) cutout(c);
    // side intake vents
    side_vents();
  }
  // added features (not subtracted)
  for (m = board_mounts) board_stud(m[0], m[1]);
  corner_screw_posts();
}


// ============================================================================
//  LID (上盖)
// ============================================================================

// vent matrix on the lid plate
module lid_vents() {
  for (i = [0 : vent_cols - 1], j = [0 : vent_rows - 1]) {
    hx = vent_cx + (i - (vent_cols - 1) / 2) * vent_spacing;
    hy = vent_cy + (j - (vent_rows - 1) / 2) * vent_spacing;
    translate([hx, hy, base_height - 0.001])
      cylinder(d = vent_hole_d, h = lid_thickness + 0.002);
  }
}

// reserved fan cutout (only active when enable_fan_cutout = true)
module fan_cutout() {
  translate([case_length/2, case_width/2, base_height - 0.001])
    cylinder(d = fan_size - 2, h = lid_thickness + 0.002);
  r = fan_size / 2;
  for (a = [45, 135, 225, 315])
    translate([case_length/2 + r*cos(a), case_width/2 + r*sin(a), base_height - 0.001])
      cylinder(d = 3.2, h = lid_thickness + 0.002);
}

module lid_solid() {
  difference() {
    union() {
      // top plate
      rounded_rect_prism(case_length/2, case_width/2, base_height,
                         case_length, case_width, corner_radius, lid_thickness);
      // locating lip (ring that drops into the base, kept off the inner wall
      // by fit_clearance per side)
      difference() {
        rounded_rect_prism(case_length/2, case_width/2,
                           base_height - lid_lip_height,
                           lip_outer_len, lip_outer_wid,
                           max(0.5, lip_outer_radius), lid_lip_height);
        rounded_rect_prism(case_length/2, case_width/2,
                           base_height - lid_lip_height - 1,
                           lip_inner_len, lip_inner_wid,
                           max(0.5, lip_inner_radius), lid_lip_height + 2);
      }
    }
    // corner screw through-holes (match the base corner posts)
    for (c = corner_posts)
      translate([c[0], c[1], base_height - 0.001])
        cylinder(d = lid_screw_clearance_d, h = lid_thickness + 0.002);
    // lid vent matrix
    lid_vents();
    // reserved fan cutout
    if (enable_fan_cutout) fan_cutout();
  }
}

// lid in print-friendly orientation: flat top plate down (on the build plate),
// locating lip pointing up
module lid_print() {
  translate([0, 0, case_height])
    rotate([180, 0, 0])
      lid_solid();
}


// ============================================================================
//  DEVICE PLACEHOLDERS & PREVIEW LABELS  (preview-only, never exported)
// ============================================================================

module device_placeholder(p) {
  color(p[8])
    translate([p[4], p[5], p[6]])
      rotate([0, 0, p[7]])
        translate([-p[1]/2, -p[2]/2, 0])
          cube([p[1], p[2], p[3]]);
}

module placeholders_solid() {
  for (p = placeholders) device_placeholder(p);
}

// flat text label placed just outside the wall on the top rim (readable from above)
module label_at(face, hpos, vpos, txt) {
  pos = (face == "front") ? [hpos, -2, base_height + 0.5]
      : (face == "back")  ? [hpos, case_width + 2, base_height + 0.5]
      : (face == "left")  ? [-2, hpos, base_height + 0.5]
      : [case_length + 2, hpos, base_height + 0.5];
  color("black")
    translate(pos)
      linear_extrude(height = 0.6)
        text(txt, size = 3, halign = "center", valign = "center");
}

// small red marker on the wall at each cutout centre
module cutout_marker(face, hpos, vpos) {
  pos = (face == "front") ? [hpos, 0, vpos]
      : (face == "back")  ? [hpos, case_width, vpos]
      : (face == "left")  ? [0, hpos, vpos]
      : [case_length, hpos, vpos];
  color("red") translate(pos) sphere(d = 2.5);
}

module labels() {
  for (c = interfaces) {
    label_at(c[0], c[1], c[2], c[6]);
    cutout_marker(c[0], c[1], c[2]);
  }
}

// lid ghosted above the base so both parts are visible in preview
module lid_floating() {
  translate([0, 0, 25]) lid_solid();
}


// ============================================================================
//  TOP-LEVEL MODE DISPATCH
// ============================================================================
if (part == "base") {
  base_shell();
} else if (part == "lid") {
  lid_print();
} else if (part == "assembly") {
  base_shell();
  lid_solid();
  %placeholders_solid();   // ghost: visible in preview, excluded from STL
  %labels();               // ghost: excluded from STL
} else if (part == "preview") {
  %base_shell();           // ghost shell so the interior is visible
  placeholders_solid();    // solid, colored
  labels();                // solid labels + markers
  %lid_floating();         // ghost lid above
}
