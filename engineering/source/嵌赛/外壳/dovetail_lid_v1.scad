// Units mm. Existing body retained at its original XYZ coordinates.
// Select body/lid/assembly/fit_body/fit_lid. Render with OpenSCAD F6.
part_id=0; // 0 assembly,1 body,2 lid,3 fit_body,4 fit_lid
clearance=0.35; // radial clearance; test your printer before full print
source="shell_original.stl";
x0=-108.00034332; length=316; depth=150; top=196;
wall=3.5; rail_center=8; rail_z=190; rail_h=6.5;
plate_t=3; gap=0.35;
ventilation=true;
// No RX hole: location and connector diameter have not been measured.
module along_x(x,len,points){
 translate([x,0,0]) rotate([90,0,90])
 linear_extrude(height=len,convexity=10) polygon(points);
}
module profile(c,bottom,upper,zlo,zhi){
 along_x(x0-1,length-wall+1,
 [[c-bottom/2,zlo],[c+bottom/2,zlo],[c+upper/2,zhi],[c-upper/2,zhi]]);
}
module rails(){
 for(c=[rail_center,depth-rail_center])
 translate([x0+wall-0.3,c-5,188]) cube([length-2*wall+0.6,10,8]);
}
module groove(c){
 profile(c,6+2*clearance,3+2*clearance,rail_z-clearance,top+gap+0.2);
}
module modified_body(){
 difference(){
  union(){import(source,convexity=20);rails();}
  groove(rail_center);groove(depth-rail_center);
 }
}
module male(c){
 // 45-ish tapered dovetail; top neck joins the lid underside.
 along_x(x0+gap,length-wall-gap-clearance,
 [[c-3,rail_z],[c+3,rail_z],[c+1.5,top+gap+0.05],[c-1.5,top+gap+0.05]]);
}
module vent_slots(){
 // Central vent groups, away from both rails. Rounded ends reduce stress.
 for(x=[x0+35:12:x0+length-35])
 for(y=[53,97])
 translate([x,y,top-1]) linear_extrude(height=plate_t+3)
 hull(){translate([0,-13])circle(r=1.4,$fn=20);translate([0,13])circle(r=1.4,$fn=20);}
}
module lid_installed(){
 difference(){
  union(){
   translate([x0+gap,gap,top+gap])cube([length-2*gap,depth-2*gap,plate_t]);
   male(rail_center);male(depth-rail_center);
  }
  if(ventilation)vent_slots();
  // Finger scallop at entry short edge, not a locking mechanism.
  translate([x0-1,depth/2,top+gap+plate_t])rotate([0,90,0])cylinder(h=6,r=9,$fn=48);
 }
}
module fit_body(){
 translate([-(x0+25),-2,-188])intersection(){
  modified_body();translate([x0+25,2,188])cube([40,14,10]);
 }
}
module fit_lid(){
 translate([-(x0+25),-2,-rail_z])intersection(){
  lid_installed();translate([x0+25,2,189])cube([40,14,12]);
 }
}
if(part_id==1)modified_body();
else if(part_id==2)translate([0,depth,top+gap+plate_t])rotate([180,0,0])lid_installed();
else if(part_id==3)fit_body();
else if(part_id==4)fit_lid();
else if(part_id==5)intersection(){modified_body();lid_installed();}
else if(part_id==6)intersection(){
 union(){
  difference(){modified_body();import(source,convexity=20);}
  difference(){import(source,convexity=20);modified_body();}
 }
 translate([x0-1,-1,-1])cube([length+2,depth+2,188.999]);
}
else if(part_id==7)intersection(){
 modified_body();
 union(){for(s=[0,1,5,20,80,160,240,315])translate([-s,0,0])lid_installed();}
}
else {color("LightSteelBlue")modified_body();color("Orange",0.85)lid_installed();}
