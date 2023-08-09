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

param PVA_module_size{u in UnitsOfType['PV']} default 1.6;		#m^2 	Viessmann
param PVA_inverter_eff{u in UnitsOfType['PV']} default 0.97;		#- 		estimation
param PVA_U_h{u in UnitsOfType['PV']} default 29.1;				#? 		[1]
param PVA_F{u in UnitsOfType['PV']} default 0.9;					#- 		[1]
param PVA_temperature_ref{u in UnitsOfType['PV']} default 298;		#K 		[1]
param PVA_efficiency_ref{u in UnitsOfType['PV']} default 0.2;		#- 		[1]
param PVA_efficiency_var{u in UnitsOfType['PV']} default 0.0012;	#- 		[1]
																									
param PVA_temperature{u in UnitsOfType['PV'],p in Period,t in Time[p]} :=
	(PVA_U_h[u]*(T_ext[p,t]+273.15))/(PVA_U_h[u] - PVA_efficiency_var[u]*I_global[p,t]) +
	I_global[p,t]*(PVA_F[u] - PVA_efficiency_ref[u] - PVA_efficiency_var[u]*PVA_temperature_ref[u])/
	(PVA_U_h[u] - PVA_efficiency_var[u]*I_global[p,t]);											#K

param PVA_efficiency{u in UnitsOfType['PV'],p in Period,t in Time[p]} :=
	PVA_efficiency_ref[u]-PVA_efficiency_var[u]*(PVA_temperature[u,p,t]-PVA_temperature_ref[u]); 	#-	

# ----------------------------------------- VARIABLES ---------------------------------------
var PVA_module_nbr{u in UnitsOfType['PV']} >= 0;
	;								#-

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to PVA_c1{h in House,u in UnitsOfType['PV'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = PVA_inverter_eff[u]*PVA_efficiency[u,p,t]*(I_global[p,t]/1000)*(Units_Mult[u]/PVA_efficiency_ref[u])- Units_curtailment['Electricity', u, p,t];  	#kW

subject to PVA_c2{h in House,u in UnitsOfType['PV'] inter UnitsOfHouse[h]}:
(Units_Mult[u]/PVA_efficiency_ref[u]) = PVA_module_size[u]*PVA_module_nbr[u];

subject to PVA_c3{h in House,u in UnitsOfType['PV'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_curtailment['Electricity', u, p,t] <= PVA_inverter_eff[u]*PVA_efficiency[u,p,t]*(I_global[p,t]/1000)*(Units_Mult[u]/PVA_efficiency_ref[u]);  #kW

subject to limits_maximal_PV_to_roof{h in House}:
sum{ui in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h]}(Units_Mult[ui]) + sum{uj in UnitsOfType['PV'] inter UnitsOfHouse[h]} (Units_Mult[uj]/PVA_efficiency_ref[uj]) <= SolarRoofArea[h];

subject to enforce_PV_max{h in House, u in UnitsOfType['PV']}:
sum{ui in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h]}(Units_Mult[ui]) + sum{uj in UnitsOfType['PV'] inter UnitsOfHouse[h]}(Units_Mult[uj]/PVA_efficiency_ref[uj]) = ((SolarRoofArea[h]) div PVA_module_size[u])*PVA_module_size[u];
#-----------------------------------------------------------------------------------------------------------------------
