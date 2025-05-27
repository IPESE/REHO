
######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Latent heat storage
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# Storage temperature is constant (no exergy degradation)

param LHS_T_Fusion default 52; # degC
param Unit_capacity default 1;
param Unit_capacity_kJ := Unit_capacity*3600  ; #kJ 
param LHS_fusion_enthalpy default 245; #KJ/Kg from stadlerThermalEnergyStorage2019
param LHS_rho default 777; #Kg/m3 from stadlerThermalEnergyStorage2019
param LHS_P_in := 1/6; #Crate
param LHS_P_out := 1/6; #Crate

param LHS_diameter{UnitsOfType['SolidLiquidLHS']} default 0.98;		#m			Viessmann (mean from Vitocell E)
param LHS_U_h{UnitsOfType['SolidLiquidLHS']} 	default 0.0013;		#kW/m2 K	[1]
param LHS_eff_ch{UnitsOfType['SolidLiquidLHS']} 	default 0.99;		#-
param LHS_eff_di{UnitsOfType['SolidLiquidLHS']} 	default 0.99;		#-
param LHS_Tamb{UnitsOfType['SolidLiquidLHS']} 	default 20;			#degC		estimated
param LHS_self_discharge{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],p in Period}:= 
	4*LHS_U_h[u]*(LHS_T_Fusion-LHS_Tamb[u])*3600/(LHS_fusion_enthalpy*LHS_diameter[u]*LHS_rho);						#T in LHSindex[h,p] diff {first(LHSindex[h,p])} }

# overall energy capacity
var LHS_E_stored{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],hy in Year} >=0;	
# Flow entering (positive energy) a layer									>= 0,<= 1e4*sum{i in House}(ERA[i]);
var LHS_mf_cold{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],p in Period,t in Time[p]}	>= 0;	#kJ/dt
# Flow leaving a layer
var LHS_mf_hot{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],p in Period,t in Time[p]} 	>= 0;	#kJ/dt

var LHS_E_max{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h]} >=0;#kJ

#-SOC
subject to LHS_c1{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h]}:
LHS_E_max[h,u] = Unit_capacity_kJ*Units_Mult[u];	#kJ

subject to LHS_c2{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],hy in Year}:
LHS_E_stored[h,u,hy] <= LHS_E_max[h,u];	#kJ

#-CHARGING/DISCHARGING (expressed in power)
subject to LHS_c3{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
LHS_mf_cold[h,u,p,t]*dt[p] <= LHS_P_in*LHS_E_max[h,u];																		#kJ																																		#kJ																																#kJ

subject to LHS_c5{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
LHS_mf_hot[h,u,p,t]*dt[p] <= LHS_P_out*LHS_E_max[h,u];																			#kJ

#-STREAMS
#-cold stream-> heat incoming
subject to LHS_energy_balance{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hout[st] = 1}:
LHS_mf_cold[h,u,p,t] =  LHS_eff_ch[u]*sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t]*dt[p]*3600;#kJ

#-hot stream heat leaving 
subject to LHS_EB_c2{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
LHS_mf_hot[h,u,p,t] = (1/LHS_eff_di[u])*sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t]*dt[p]*3600;#kJ


#-ENERGY BALANCES
subject to LHS_MB_c1{h in House,u in UnitsOfType['SolidLiquidLHS'] inter UnitsOfHouse[h],hy in Year}:
(LHS_E_stored[h,u,next(hy,Year)] - LHS_E_stored[h,u,hy]) =  
+ (-LHS_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy]] + LHS_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy]] - LHS_self_discharge[h,u,PeriodOfYear[hy]]*LHS_E_stored[h,u,hy])*dt[PeriodOfYear[hy]]; 						#kg
