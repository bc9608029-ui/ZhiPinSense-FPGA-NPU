# Rough Enclosure v1 (prep2) — 下壳/上盖 (base + lid)

## Improved1 safety revision

This independent work tree adds mechanical fail-fast checks and structural
reinforcement without claiming measured fit:

- studs/posts overlap the floor by 0.20 mm so Boolean unions are not merely
  coplanar;
- tall corner posts are 10 mm OD and have two wall-connecting ribs;
- the provisional M3 plastic pilot (2.7 mm) is separated from the lid clearance
  hole (3.4 mm), instead of reusing one 3.2 mm diameter for incompatible roles;
- assertions reject impossible shell, lip, mount and fastener parameters;
- warnings report insufficient printer-bed margin and preview solids that cross
  an inner wall.

With the current placeholder values the audit intentionally reports both:
`WARNING_PRINT_BED_MARGIN` and
`WARNING_PLACEHOLDER_INTERSECTS_WALL label=pluto-sdr`. These are unresolved
measurement/layout blockers, not export failures. Do not suppress them by moving
parts until the physical hardware and usable printer bed are measured.

Validated improved1 exports:

- `rough_enclosure_improved1_base.stl`
- `rough_enclosure_improved1_lid.stl`
- `validation/improved1_assembly_v2.stl`
- `fit_test_m3_post.stl`

All four report `Simple: yes`; the independent audit records zero zero-area
triangles, zero boundary/non-manifold edges, and one connected component each.
They remain dimensional prototypes, not final fitted parts.

**Status: `M29-RML23-ENCLOSURE-PREP2-ROUGH-MESH-READY-FOR-DIMENSION-VALIDATION`** (highest allowed).

**This model MUST NOT be treated as a final fitted enclosure (不可直接视为最终适配外壳).** It is a parameterized rough model whose dimensions are PLACEHOLDER values, not measurements. Nothing here is dimension-verified, print-fit-verified, or assembly-verified.

- Every default dimension in the `.scad` sources is a **placeholder**, flagged **待实测** (to-be-measured).
- Only the internal hardware is in scope: Linux/NPU main board, the board-side RX Pluto SDR, service cables (power/ethernet/serial/USB), SMA connectors and their bend space. The PC-side TX Pluto is NOT inside this enclosure.
- The `.scad` source is the master; STLs are always exported from it (never hand-edited).

## Files

| File | Purpose |
|---|---|
| `rough_enclosure_v1.scad` | Parameterized enclosure source (master) |
| `fit_test_lip.scad` | Lip / base-wall slip-fit test piece |
| `fit_test_rj45_wall.scad` | RJ45 cutout test plate |
| `fit_test_sma_wall.scad` | SMA cutout test plate |
| `fit_test_m3_post.scad` | M3 printed-post pilot coupon (2.5 / 2.7 / 2.9 mm) |
| `dimensions_template.tsv` | Dimension ledger: placeholder vs. measured |
| `rough_enclosure_v1_{base,lid,assembly}.stl` | Export artifacts (see export status) |
| `renders\*.png` | 4 preview renders (see export status) |

### Export status — honest

- **OpenSCAD 2021.01 is installed** and was used via `C:\Program Files\OpenSCAD\openscad.com` (the console wrapper — `openscad.exe` is the GUI app and does not wait in PowerShell). Exports are driven by `export_enclosure.ps1`, which substitutes `part = "…"` in a temp copy of the master (Windows PowerShell/Qt mangles `-D 'part="base"'` quoting, so `-D` is avoided).
- **STL export: RUN** — `base`, `lid`, `assembly` + the 3 fit-test pieces exported; every mesh reports **"Simple: yes"** (2-manifold, closed).
- **PNG render: RUN** — 4 previews exported and **byte-deterministic** (two runs → identical SHA-256).
- **STL byte-determinism: NOT-REPRODUCIBLE** — OpenSCAD/CGAL emits the *same mesh* (identical vertex/facet counts, "Simple: yes") but the Nef→Polyhedron triangle *order* differs run to run, so the STL SHA-256 is a per-run value, not a content fingerprint. The vertex/facet counts + manifoldness are the stable identity.
- **Independent mesh lint (normals / zero-area / self-intersection / bbox): NOT-RUN** — no blender/admesh/assimp/meshlab is installed; "Simple: yes" is OpenSCAD's own manifold report only.

Deterministic two-run result (`export_enclosure.ps1`, OpenSCAD 2021.01):

PNG (stable content fingerprints):
```
F3BF835F3099AAC3A0DCF265762782FF472F103283591FD5AB6AAA99A2CA56E2  assembly_isometric.png
9DC965ADD89C4D196DC4A3F7A70B428A9B68078EC09F3BAC64595D25DD0C7511  base_isometric.png
467EE544A2334FFBC0E7D67BB59397B8A8E514F5041E15F20C260DE53E892203  internal_layout.png
C560C3A46060C68C923E0E5CEED610ED0307E312ECE22E2DCBB271248FD30F4D  lid_isometric.png
```

STL (non-reproducible SHA — two runs differ; keep the counts, not the SHA):
```
run1 9F63C5C0DCA9…  fit_test_lip.stl          run2 A22376F825AB…
run1 BE1DCCFE5ED3…  fit_test_rj45_wall.stl    run2 BF5F29030AAB…
run1 C5C1E01D843A…  fit_test_sma_wall.stl     run2 E3A85BFB55F8…
run1 D6461CEA182E…  rough_enclosure_v1_assembly.stl   run2 EDA464DF22CA…
run1 49219B6AF4B6…  rough_enclosure_v1_base.stl       run2 098A60E6B422…
run1 832D78CF8D04…  rough_enclosure_v1_lid.stl        run2 4EF5BEA61292…
```

Stable STL geometry identity (identical across both runs):

| Mesh | Vertices | Facets | Volumes | Manifold |
|---|---|---|---|---|
| base | 4672 | 2355 | 2 | Simple: yes |
| lid | 11400 | 5704 | 2 | Simple: yes |
| assembly | 15344 | 7690 | 2 | Simple: yes |
| fit_test_lip | 24 | 16 | 3 | Simple: yes |
| fit_test_rj45_wall | 160 | 82 | 2 | Simple: yes |
| fit_test_sma_wall | 152 | 78 | 2 | Simple: yes |

## Coordinate convention

- X = length (0 … `case_length`), Y = width (0 … `case_width`), Z = up.
- Faces: `front` = y=0, `back` = y=`case_width`, `left` = x=0, `right` = x=`case_length`.
- Unified origin for `dimensions_template.tsv`: case front-left OUTER corner (x=0, y=0), z=0 = base bottom face.
- Base height is derived: `base_height = case_height - lid_thickness`. The lid is a top plate + locating lip that drops into the base, so total assembled height equals `case_height`.

## How to change L / W / H

Edit the single parameter block at the **top** of `rough_enclosure_v1.scad`:

```openscad
case_length = 220;
case_width  = 160;
case_height = 70;
```

Base, lid, lip, corner radii, vent centre, and corner-post positions all recompute. Note: interface cutout and vent positions are placeholder absolute coordinates — if you shrink the outer size below ~L=190 / W=140 you must also move those arrays (see below); the geometry itself stays valid (no crash).

## How to move the device placeholders

Placeholders are visual/interference-check solids only — they are **never** part of base/lid/assembly STLs (they use the `%` ghost modifier, and are not called at all in `base`/`lid` modes). Edit the `placeholders` list:

```openscad
placeholders = [
  ["main-board", 130, 95, 20,  82, 95, base_thickness + stud_height, 0, "limegreen"],
  ["pluto-sdr",   70, 45, 20, 183, 33, base_thickness,               0, "dodgerblue"],
  ["cable-bend",  40, 30, 30, 190, 95, base_thickness,               0, "orange"]
];
```

Field order: `[label, length, width, height, pos_x, pos_y, pos_z, rot_z, color]`. `pos_x/pos_y` = block centre, `pos_z` = bottom face height, `rot_z` = Z rotation in degrees.

## How to edit the mounting holes (board studs)

Edit `board_mounts` (moving a stud is an array edit only):

```openscad
board_mounts = [[27,57],[137,57],[27,133],[137,133]];   // [x,y] pairs
```

Stud geometry (M3): `stud_od` (7), `stud_height` (6), `stud_pilot_d` (2.7,
provisional self-tap pilot, blind). The corner post uses a separate 2.7 mm pilot,
while the lid uses a 3.4 mm clearance hole. Validate the chosen screw/insert with
a printed coupon before printing the full shell.

## How to add / remove / move interfaces

All cutouts live in one `interfaces` array:

```openscad
[face, hpos, vpos, w_or_d, h, r_or_type, "label"]
```

- `face`: `"front" | "back" | "left" | "right"`; `hpos`/`vpos`: centre along the face / height above the base floor.
- `w_or_d`: rectangle width, or hole **diameter** when `h <= 0` (round hole, e.g. SMA); `h`: rectangle height (0 for round).
- `r_or_type`: corner radius for rectangles (0 = sharp), ignored for round holes; `label`: name shown in preview.

Add/delete a row to add/remove a cutout; change `hpos/vpos` to move one. No per-cutout copy-paste geometry.

## How to select base / lid / assembly / preview

```openscad
part = "assembly";   // "assembly" | "base" | "lid" | "preview"
```

- `base` — base only. `lid` — lid only, print-friendly orientation (flat plate down, lip up).
- `assembly` — base + lid together; placeholders ghosted (excluded from STL).
- `preview` — see-through shell + solid placeholders + interface labels/markers.

## Fit-test pieces (prep2) — print these first

Print these small pieces before the whole shell, to validate tolerance and cutout sizes:

| File | What it validates | How to check |
|---|---|---|
| `fit_test_lip.scad` | lid-lip slip fit (0.35 mm/side) and 1.6 mm lip printability | Press the lip bar's outer face against the wall bar's inner face; should slide with light resistance, no slop |
| `fit_test_rj45_wall.scad` | RJ45 cutout size (16×14 r2 placeholder) | Pass an actual RJ45 jack/plug through the hole |
| `fit_test_sma_wall.scad` | SMA hole diameter (6.5 placeholder) | Pass the actual SMA bulkhead connector through |
| `fit_test_m3_post.scad` | M3 self-tap pilot against actual screw/material/profile | Test 2.5 / 2.7 / 2.9 mm posts; choose the smallest that accepts the screw without splitting |

Each file has its own small parameter block (marked "keep in sync with rough_enclosure_v1.scad"). Update the test piece AND the main file together when you measure real values.

## How to export STL

### GUI (recommended)

1. Open the `.scad` in OpenSCAD, set `part`, press **F6** (Render), then **File → Export → Export as STL**.
2. `part="base"` → `rough_enclosure_v1_base.stl`; `part="lid"` → `rough_enclosure_v1_lid.stl`; `part="assembly"` → `rough_enclosure_v1_assembly.stl`.
3. Renders: set `part`, position the view, then **File → Export → Export as PNG** (or F5 preview + screenshot).

### CLI export (on this Windows machine, use `export_enclosure.ps1`)

On this machine, run `powershell -NoProfile -File export_enclosure.ps1` — it substitutes `part = "…"` in a temp copy (the `-D 'part="base"'` form below is mangled through Windows PowerShell/Qt and produces "top level object is empty"). The POSIX-shell commands below work on Linux/macOS only:

```bash
openscad -o rough_enclosure_v1_base.stl     -D 'part="base"'     rough_enclosure_v1.scad
openscad -o rough_enclosure_v1_lid.stl      -D 'part="lid"'      rough_enclosure_v1.scad
openscad -o rough_enclosure_v1_assembly.stl -D 'part="assembly"' rough_enclosure_v1.scad
openscad -o renders/assembly_isometric.png --imgsize=1600,1200 -D 'part="assembly"' rough_enclosure_v1.scad
openscad -o renders/base_isometric.png     --imgsize=1600,1200 -D 'part="base"'     rough_enclosure_v1.scad
openscad -o renders/lid_isometric.png      --imgsize=1600,1200 -D 'part="lid"'      rough_enclosure_v1.scad
openscad -o renders/internal_layout.png    --imgsize=1600,1200 -D 'part="preview"'  rough_enclosure_v1.scad
```

After export: record `openscad --version` and the SHA-256 of every STL/PNG. Re-run twice to confirm the PNGs are byte-identical; the STLs will differ in triangle order despite identical geometry (see "Export status" above) — treat the vertex/facet counts + manifoldness, not the STL SHA, as the mesh identity.

## Static parameter check report (prep2, arithmetic/source review only)

Defaults L=220, W=160, H=70. `base_height = H - lid_thickness = 67.6`. Derived: inner cavity 215.2×155.2 (r=5.6); lip outer 214.5×154.5 (r=5.25); lip inner 211.3×151.3 (r=3.65); per-side lip clearance 0.35.

| # | Constraint | Result |
|---|---|---|
| 1 | L / W / H change independently, geometry stays legal | PASS (arithmetic) — derived dims stay positive for L≥60, W≥50, H≥20; cutout/vent positions are placeholder and must be re-checked if outer dims shrink below ~L=190 / W=140 |
| 2 | base_height > 0 | PASS — 67.6 (= case_height − lid_thickness) |
| 3 | corner radius within outer constraint | PASS — 8 < min(L,W)/2 = 80; inner 5.6, lip outer 5.25, lip inner 3.65 all > 0 |
| 4 | wall_thickness ≥ 2.0 | PASS — 2.4 |
| 5 | base_thickness ≥ 2.4 | PASS — 3.0 |
| 6 | studs do not pierce the base floor | PASS — studs sit on z=base_thickness (3), pilot holes blind |
| 7 | screw holes non-zero and do not pierce the floor | PASS — stud 3.2 and corner-post 3.2 blind holes (corner depth 12 < post height 64.6) |
| 8 | lid lip positive tolerance | PASS — lip footprint 214.5 < cavity 215.2, +0.35 mm/side |
| 9 | interface cutouts fully pierce the side wall | PASS — all cutters 3× wall thickness, centred on the wall |
| 10 | placeholders not in formal STL | PASS — `%` ghost modifier; never called in base/lid modes |
| 11 | no zero-thickness faces / coplanar boolean cuts | PASS (design) — cavity opens past rim by +1 mm; cuts offset by ±0.001/±0.002 to avoid coincident faces |

These are static/arithmetic conclusions. The prep2 meshes were rendered with
OpenSCAD and reported `Simple: yes`; independent checks for normals, zero-area
facets, self-intersection and exact bounding boxes remain separate checks. The
previous sentence claiming that OpenSCAD was not installed was stale and has
been removed in this improved copy.

## Suggested print settings

- Material: **PETG preferred** (PLA OK for a size trial). Layer **0.20 mm**, nozzle **0.4 mm**.
- Walls **3–4**, bottom layers **4–5**, infill **15–25 %**.
- Supports **off where possible** (base is open-top; the lid lip is a short 1.6 mm wall; test pieces print flat).
- Print the **fit-test pieces first** (lip + RJ45 + SMA) before the whole box.
- No snap clips — the lid is held by 4 corner M3 screws into the corner posts.

## What you must measure next (待实测)

Record into `dimensions_template.tsv` (fill `measured_value_mm`, flip `status` to `measured`, then `verified` only after a successful print test):

1. Main-board L/W/H, its bottom-to-tallest-component height, and the 4 mounting-hole X/Y relative to the case origin.
2. Heatsink height.
3. RX Pluto L/W/H, its mount position, and its fixation method.
4. RJ45 / USB / serial / power connector centres and envelopes (plug + clearance).
5. Two SMA centres, heights above the floor, and hole diameters.
6. Each cable's plug size and minimum bend space/radius.
7. Fan requirement (if any) and vent sizing.
8. Switch / LED positions.
9. Assembly tool space (e.g. screwdriver reach at the corner screws).
10. Final wall_thickness, corner_radius, fit_clearance, lid_lip values.

## Verification status (honest)

| Check | Result |
|---|---|
| Static parameter check (11 constraints above) | PASS (arithmetic/source review only) |
| STL export (base/lid/assembly) | RUN — all "Simple: yes" (manifold); byte non-deterministic |
| PNG renders (4) | RUN — byte-deterministic (two runs → identical SHA-256) |
| Mesh check (manifold / closed) | PARTIAL — OpenSCAD "Simple: yes" for all 6 pieces; independent lint NOT-RUN |
| Mesh check (normals / zero-area / self-intersection / bbox) | NOT-RUN — no blender / admesh / assimp / meshlab |
| Fit-test piece STLs | RUN — lip / rj45 / sma all "Simple: yes" |
| OpenSCAD version | 2021.01 |

## Red lines honored

- No electronics/software project touched (pure CAD, isolated in `F:\嵌赛\enclosure_cad\`).
- Placeholder dimensions are explicitly marked unmeasured everywhere.
- No claim of adaptation to the real board or of a final fitted enclosure.
- No snap clips; no placeholders imported into any STL geometry; `.scad` kept as master; no later measured version overwritten.
