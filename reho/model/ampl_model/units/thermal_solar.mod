######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---SOLAR THERMAL COLLECTOR MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static solar thermal panel model including:
#	1. temperature dependant efficiency and output
#-References : 
# [1]	J. Rager, PhD Thesis, 2015.
# [2]	J. Duffie and W. Beckmann, Solar Engineering of Thermal Processes, 4th edition, pp. 294.
# -------------------------------------------- SETS ------------------------------------------
param STC_dTmin := 7;
set STCindex ordered by Reals:= {55 + STC_dTmin};

# ----------------------------------------- PARAMETERS ---------------------------------------
param STC_module_size{u in UnitsOfType['ThermalSolar']}>=0 default 2.32;		#m^2		Viessmann
param STC_a{u in UnitsOfType['ThermalSolar']}>=0 default 4.16;				#W/m^2 K 	SPF (Viessmann, Vitosol 200-F)
param STC_b{u in UnitsOfType['ThermalSolar']}>=0 default 0.0073;				#W/m^2 K^2	SPF (Viessmann, Vitosol 200-F)
param STC_efficiency_ref{u in UnitsOfType['ThermalSolar']}>=0 default 0.836;	#-			SPF (Viessmann, Vitosol 200-F)
param STC_Tlm{u in UnitsOfType['ThermalSolar'],T in STCindex,p in Period,t in Time[p]} := sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t]=T}( (Streams_Tin[st,p,t]-Streams_Tout[st,p,t])/(log(Streams_Tin[st,p,t]+273.15)-log(Streams_Tout[st,p,t]+273.15))-(T_ext[p,t]+273.15) );	#K

#-Definition from [2]
param STC_efficiency{u in UnitsOfType['ThermalSolar'],T in STCindex,p in Period,t in Time[p]} :=
if I_global[p,t] >0 and STC_efficiency_ref[u] - STC_a[u]*(STC_Tlm[u,T,p,t]/I_global[p,t]) - STC_b[u]*(STC_Tlm[u,T,p,t]^2/I_global[p,t]) > 0 then 
	STC_efficiency_ref[u] - STC_a[u]*(STC_Tlm[u,T,p,t]/I_global[p,t]) - STC_b[u]*(STC_Tlm[u,T,p,t]^2/I_global[p,t]) 
else 
	0;

# ----------------------------------------- VARIABLES ---------------------------------------
var STC_Area_T{u in UnitsOfType['ThermalSolar'],STCindex,p in Period,t in Time[p]}>= 0,<= sum{h in House}(ERA[h]);		#m2
var STC_module_nbr{u in UnitsOfType['ThermalSolar']} >= 0, integer;

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to STC_EB_c1{h in House,u in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],T in STCindex,p in Period,t in Time[p]: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = STC_Area_T[u,T,p,t]*STC_efficiency[u,T,p,t]*(I_global[p,t]/1000);	#kW

#--Sizing
subject to STC_c1{h in House,u in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in STCindex} (STC_Area_T[u,T,p,t]) <= Units_Mult[u];																	#m2

subject to STC_c2{h in House,u in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h]}:
Units_Mult[u] = STC_module_size[u]*STC_module_nbr[u];																		#m2			

subject to enforce_DHW_tank_if_thermal_solar{h in House}:
sum{uj in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]} Units_Use[uj] >= sum{ui in UnitsOfType['ThermalSolar'] inter UnitsOfHouse[h]} Units_Use[ui];

#-----------------------------------------------------------------------------------------------------------------------
