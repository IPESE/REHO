######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---IRRADIATION MODEL - SKYDOME, ORIENTATION PV PANEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

set Patches default {0.. 144}; #Skydome patches
set SurfaceTypes default {'Flat_roof', 'Facades'};
set Surface default {1};

#--------------------------------------------------------------------------------------------------------------------#
# Subsets
set SurfaceOfHouse{House} within Surface default {1}; # Envelope of House
#set HouseOfSurface{s in Surface} ordered within House := setof{h in House, soh in SurfaceOfHouse[h]: s= soh} h;

set SurfaceOfType{SurfaceTypes} within Surface default{}; #Type of Surface f.e Flat Roof or Facades
set ConfigOfSurface{s in Surface} dimen 2 default {(180,0)}; #Configuration possibilities 

#--------------------------------------------------------------------------------------------------------------------#
# Input Parameter describing Skydome e: elevation of patch a: azimuth of patch
param Sin_e{pt in Patches}; 
param Cos_e{pt in Patches};

param Sin_a{pt in Patches};
param Cos_a{pt in Patches};
param Irr{pt in Patches, p in Period, t in Time[p]};
#--------------------------------------------------------------------------------------------------------------------#
# aid parameter for trigonomie calculation
param pi := 4*atan(1);
param deg_rad := 2*pi / 360; 
param Elevation_angle{pt in Patches}= acos(Cos_e[pt])/deg_rad;
#--------------------------------------------------------------------------------------------------------------------#
#---Orientate surface in skydome
#--------------------------------------------------------------------------------------------------------------------#
#rotation of the PV panel, negative values for patches which cannot be "seen" from the panel
param Rotation{s in Surface, (az,ti) in ConfigOfSurface[s],pt in Patches} :=
	max(sin(deg_rad*az)*sin(deg_rad*ti)*Sin_a[pt]*Cos_e[pt] + cos(deg_rad*az)*sin(deg_rad*ti)*Cos_a[pt]*Cos_e[pt]+cos(deg_rad*ti)*Sin_e[pt],0); 

#--------------------------------------------------------------------------------------------------------------------#
#---Panel Arrangement and Mutual Shading
#--------------------------------------------------------------------------------------------------------------------#
param Design_lim_angle default 20; #[3]: OPTIMIZATION OF ROW-ARRANGEMENT IN PV SYSTEMS, SHADING LOSS EVALUATIONS ACCORDING TO MODULE POSITIONING AND CONNEXIONS
param PVA_module_height{u in UnitsOfType['PV']} default 1.0; #	[2]:  Mitsubishi Electric Module PV-MLU255HC
param PVA_module_width{u in UnitsOfType['PV']} default 1.6;# 1.6[2] 
param PVA_module_distance{u in UnitsOfType['PV'], s in Surface, (az,ti) in ConfigOfSurface[s]}:= if s in SurfaceOfType['Flat_roof']
	then sin(ti*deg_rad)/tan(Design_lim_angle *deg_rad)*PVA_module_height[u] else 0 ; 
param PVA_module_coverage{h in House, u in UnitsOfType['PV'] inter UnitsOfHouse[h],s in SurfaceOfHouse[h], (az,ti)in ConfigOfSurface[s]}:= (if s in SurfaceOfType['Flat_roof']
		then(PVA_module_distance[u,s,az,ti] + cos(ti*deg_rad)* PVA_module_height[u]) * PVA_module_width[u]   
		else PVA_module_height[u]*PVA_module_width[u]);

#--------------------------------------------------------------------------------------------------------------------#
#--- Mutual Shading and linerization evaluation skydpme 
#--------------------------------------------------------------------------------------------------------------------#

param Limiting_angle_shadow {h in  House, pt in Patches} default 0;

param Limiting_angle{h in  House, s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s],pt in Patches} := 
 if s in SurfaceOfType['Flat_roof'] then  atan((Cos_a[pt]*cos(az*deg_rad) + Sin_a[pt]*sin(az*deg_rad)) *tan(Design_lim_angle*deg_rad))/deg_rad 
 else ( 
	if s in SurfaceOfType['Facades'] then Limiting_angle_shadow[h,pt] #Limiting_angle_shadow[ first(HouseOfSurface[s]),pt]
	else   0);

param unshaded_share{h in  House, s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s],pt in Patches}:=
 if s in (SurfaceOfType['Flat_roof'] union SurfaceOfType['Facades']) then (if Elevation_angle[pt]<= (Limiting_angle[h,s,az,ti,pt]-6)  then 0 else ( if  Elevation_angle[pt]>= (Limiting_angle[h,s,az,ti,pt]+6) then 1 else (Elevation_angle[pt]-Limiting_angle[h,s,az,ti,pt]+6)/12)) 
 else 1;
#--------------------------------------------------------------------------------------------------------------------#
#--- Irradiation density on oriented panel W/m2
#--------------------------------------------------------------------------------------------------------------------#
param Irr_pv {h in House, s in SurfaceOfHouse[h], (az,ti)in ConfigOfSurface[s], p in Period, t in Time[p] } :=   sum{pt in Patches}unshaded_share[h,s,az,ti,pt] *Rotation[s,az,ti,pt]*Irr[pt,p,t] ; 
param Irr_pv_without_loss {h in House, s in SurfaceOfHouse[h], (az,ti)in ConfigOfSurface[s], p in Period, t in Time[p] } :=   sum{pt in Patches}Rotation[s,az,ti,pt]*Irr[pt,p,t] ;
######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---PV PANEL MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static photovoltaic array model including:
# 	1. temperature dependant efficiency
# 	2. curtailment capabilities
#-References : 
# [1]	A. Ashouri et al., 2014
# ----------------------------------------- PARAMETERS ---------------------------------------
	
param PVA_inverter_eff{u in UnitsOfType['PV']} default 0.97;		#- 		estimation
param PVA_U_h{u in UnitsOfType['PV']} default 29.1;				#? 		[1]
param PVA_F{u in UnitsOfType['PV']} default 0.9;					#- 		[1]
param PVA_temperature_ref{u in UnitsOfType['PV']} default 298;		#K 		[1]
param PVA_efficiency_ref{u in UnitsOfType['PV']} default 0.2;		#- 		[1]
param PVA_efficiency_var{u in UnitsOfType['PV']} default 0.0012;	#- 		[1]

param HouseSurfaceArea{h in House, s in SurfaceOfHouse[h]} default ERA[h]/3;

																									
#param PVA_temperature{u in UnitsOfType['PV'],p in Period,t in Time[p]} :=
#	(PVA_U_h[u]*(T_ext[p,t]+273.15))/(PVA_U_h[u] - PVA_efficiency_var[u]*(I_global[p,t])) +
#	(I_global[p,t])*(PVA_F[u] - PVA_efficiency_ref[u] - PVA_efficiency_var[u]*PVA_temperature_ref[u])/
#	(PVA_U_h[u] - PVA_efficiency_var[u]*(I_global[p,t]));											#K

#param PVA_efficiency{u in UnitsOfType['PV'],p in Period,t in Time[p]} :=
#	PVA_efficiency_ref[u]-PVA_efficiency_var[u]*(PVA_temperature[u,p,t]-PVA_temperature_ref[u]); 	#-	

param PVA_temperature{h in House, u in UnitsOfType['PV'],s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} :=
	(PVA_U_h[u]*(T_ext[p,t]+273.15))/(PVA_U_h[u] - PVA_efficiency_var[u]*(Irr_pv[h,s,az,ti,p,t])) +
	(Irr_pv[h,s,az,ti,p,t])*(PVA_F[u] - PVA_efficiency_ref[u] - PVA_efficiency_var[u]*PVA_temperature_ref[u])/
	(PVA_U_h[u] - PVA_efficiency_var[u]*(Irr_pv[h,s,az,ti,p,t]));											#K

param PVA_efficiency{h in House,u in UnitsOfType['PV'], s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} :=
	PVA_efficiency_ref[u]-PVA_efficiency_var[u]*(PVA_temperature[h,u,s,az,ti,p,t]-PVA_temperature_ref[u]); 	#-	

# ----------------------------------------- VARIABLES ------------------------------------------------------------#
var PVA_module_nbr{h in House, s in SurfaceOfHouse[h],(az,ti) in ConfigOfSurface[s], u in UnitsOfType['PV'] inter UnitsOfHouse[h] } >=0;

var PV_electricity{h in House,u in UnitsOfType['PV'], s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} >=0;
var PV_electricity_without_loss{h in House,u in UnitsOfType['PV'], s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} >=0;
	#
# ---------------------------------------- CONSTRAINTS -----------------------------------------------------------#

subject to PV_elec{h in House,u in UnitsOfType['PV'] inter UnitsOfHouse[h], s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} :
	PV_electricity[h,u,s,az,ti,p,t] = PVA_inverter_eff[u]*PVA_efficiency[h,u,s,az,ti,p,t]*(Irr_pv[h,s,az,ti,p,t]/1000)*PVA_module_nbr[h, s, az,ti, u]*PVA_module_height[u]*PVA_module_width[u];

subject to PV_elec_loss{h in House,u in UnitsOfType['PV'] inter UnitsOfHouse[h], s in SurfaceOfHouse[h], (az,ti) in ConfigOfSurface[s], p in Period,t in Time[p]} :
	PV_electricity_without_loss[h,u,s,az,ti,p,t] = PVA_inverter_eff[u]*PVA_efficiency[h,u,s,az,ti,p,t]*(Irr_pv_without_loss[h,s,az,ti,p,t]/1000)*PVA_module_nbr[h, s, az,ti, u]*PVA_module_height[u]*PVA_module_width[u];

subject to PVO_c1{h in House, u in UnitsOfType['PV'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_supply['Electricity', u, p,t] =
	sum {s in SurfaceOfHouse[h], (az,ti)  in ConfigOfSurface[s]} PV_electricity[h,u,s,az,ti,p,t]
	 - Units_curtailment['Electricity', u, p,t];

subject to PVO_c2{h in House, u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
(Units_Mult[u]/PVA_efficiency_ref[u]) = 
	sum {s in SurfaceOfHouse[h], (az,ti)  in ConfigOfSurface[s]} (PVA_module_height[u]*PVA_module_width[u])*PVA_module_nbr[h,s,az,ti,u]; 

subject to limits_maximal_PV_to_roof{h in House, s in SurfaceOfHouse[h]  diff SurfaceOfType['Facades'], u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
HouseSurfaceArea[h,s] >=
	sum{ (az,ti)  in ConfigOfSurface[s]} PVA_module_coverage[h,u,s,az,ti] *PVA_module_nbr[h,s,az,ti,u]; #footprint not module area

subject to limits_maximal_PV_to_fac{h in House, s in SurfaceOfHouse[h]  inter SurfaceOfType['Facades'], u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
HouseSurfaceArea[h,s] >= 
	sum{ (az,ti)  in ConfigOfSurface[s]} PVA_module_coverage[h,u,s,az,ti] *PVA_module_nbr[h,s,az,ti,u]; 

subject to PVO_c4{h in House, u in UnitsOfType['PV'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
 Units_curtailment['Electricity', u, p,t] <=  PVA_inverter_eff[u]*
	sum {s in SurfaceOfHouse[h], (az,ti)  in ConfigOfSurface[s]} (PVA_efficiency[h,u,s,az,ti,p,t]*(Irr_pv[h,s,az,ti,p,t]/1000)*PVA_module_nbr[h, s, az,ti, u]*PVA_module_height[u]*PVA_module_width[u]);

subject to enforce_PV_max{h in House, s in SurfaceOfHouse[h] diff SurfaceOfType['Facades'] ,u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
HouseSurfaceArea[h,s] = ( sum{ (az,ti) in ConfigOfSurface[s]}  PVA_module_coverage[h,u,s,az,ti]*PVA_module_nbr[h,s, az,ti,u]);

subject to enforce_PV_max_fac{h in House, s in SurfaceOfHouse[h] inter SurfaceOfType['Facades'] ,u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
HouseSurfaceArea[h,s] = ( sum{ (az,ti) in ConfigOfSurface[s]}  PVA_module_coverage[h,u,s,az,ti]*PVA_module_nbr[h,s, az,ti,u]);
#-----------------------------------------------------------------------------------------------------------------------
