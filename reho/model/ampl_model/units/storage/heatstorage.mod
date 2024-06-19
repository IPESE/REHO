######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Heat storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-First-order buffer tank model including:
#	1. dis-/charging efficiencies 
#	2. self-discharging efficiency 
#	3. Temperature discretization (variable mass)
#-Definitions :
#	1. losses -> mass leaving T to T-1, here (mass) from point of view of T
#-References : 
# [1]	J. Rager, PhD Thesis, 2015.

param TES_T_min{h in House,p in Period} default 20;																											#deg C															
param TES_T_max{h in House,p in Period} := min{Thp in HP_Tsupply: Thp >= min( max{t in Time[p]} Th_supply[h,p,t], max{i in HP_Tsupply} i)} Thp;	#deg C
param TES_T_ret{h in House,p in Period} := (T_comfort_min_0[h] + TES_T_max[h,p]*(alpha_h[h]*Mcp_0h[h]))/(1+alpha_h[h]*Mcp_0h[h]);									#deg C

set TESindex{h in House,p in Period} ordered by Reals := {TES_T_max[h,p],TES_T_ret[h,p]};																	#deg C

param TES_dT{h in House,p in Period,T in TESindex[h,p] diff {first(TESindex[h,p])} } := T - prev(T,TESindex[h,p]);											#deg C

param TES_diameter{UnitsOfType['WaterTankSH']} default 0.98;		#m			Viessmann (mean from Vitocell E)
param TES_U_h{UnitsOfType['WaterTankSH']} 	default 0.0013;		#kW/m2 K	[1]
param TES_eff_ch{UnitsOfType['WaterTankSH']} 	default 0.99;		#-
param TES_eff_di{UnitsOfType['WaterTankSH']} 	default 0.99;		#-
param TES_Tamb{UnitsOfType['WaterTankSH']} 	default 20;			#degC		estimated
param TES_efficiency{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,T in TESindex[h,p] diff {first(TESindex[h,p])} }:=
	4*TES_U_h[u]*(T-TES_Tamb[u])*3600/(cp_water_kj*TES_diameter[u]*rho_water*TES_dT[h,p,T]);						#-
	
var TES_Mass{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],TESindex[h,p]} 										>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg
var TES_mf_cold{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])}}	>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg/h
var TES_mf_hot{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])}} 	>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg/h

#-SOC
subject to TES_c1{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in TESindex[h,p]} TES_Mass[h,u,p,t,T] = rho_water*Units_Mult[u];														#kg

subject to TES_c2{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in TESindex[h,p]}(T*TES_Mass[h,u,p,t,T]) >= if (T_ext[p,t] <= -70) then rho_water*Units_Mult[u]*Th_return[h,p,t] else rho_water*Units_Mult[u]*first(TESindex[h,p]);

#-CHARGING/DISCHARGING
subject to TES_c3{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])} }:
TES_mf_cold[h,u,p,t,T]*dt[p] <= TES_Mass[h,u,p,t,T];																		#kg																

subject to TES_c4{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])} }:
TES_mf_hot[h,u,p,t,T]*dt[p] <= TES_Mass[h,u,p,t,T];																			#kg

# subject to TES_c4b{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p]),last(TESindex[h,p])} }:
# TES_mf_hot[h,u,p,t,T]*dt[p] <= 0;																							#kg

#-STREAMS
#-cold stream from T-1 to T -> heat (mass) incoming to the slice T, here from point of view of T
subject to TES_energy_balance{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])}: Streams_Tout[st,p,t] = T and Streams_Hout[st] = 1}:
TES_mf_cold[h,u,p,t,T] = (TES_eff_ch[u])*(sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p]*3600/( cp_water_kj*TES_dT[h,p,T] );		#kg

#-hot stream from T to T-1 -> heat (mass) leaving to the slice T, here from point of view of T
subject to TES_EB_c2{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in TESindex[h,p] diff {first(TESindex[h,p])}: Streams_Tin[st,p,t] = T and Streams_Hin[st] = 1}:
TES_mf_hot[h,u,p,t,T] = (1/TES_eff_di[u])*(sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p]*3600/( cp_water_kj*TES_dT[h,p,T] );		#kg

#-ENERGY BALANCES
#-Middle
subject to TES_MB_c1{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in Time[p] diff {last(Time[p])},T in TESindex[h,p] diff {first(TESindex[h,p]),last(TESindex[h,p])} }:
(TES_Mass[h,u,p,t+1,T] - TES_Mass[h,u,p,t,T]) =  
+ (TES_mf_hot[h,u,p,t,next(T,TESindex[h,p])] + TES_mf_cold[h,u,p,t,T] + TES_efficiency[h,u,p,next(T,TESindex[h,p])]*TES_Mass[h,u,p,t,next(T,TESindex[h,p])])*dt[p]
- (TES_mf_hot[h,u,p,t,T] + TES_mf_cold[h,u,p,t,next(T,TESindex[h,p])] + TES_efficiency[h,u,p,T]*TES_Mass[h,u,p,t,T])*dt[p]; 						#kg

#-Bottom
subject to TES_MB_c2{h in House,u in (UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]),p in Period,t in Time[p] diff {last(Time[p])} }:
(TES_Mass[h,u,p,t+1,first(TESindex[h,p])] - TES_Mass[h,u,p,t,first(TESindex[h,p])]) =  
+ (TES_mf_hot[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])] + TES_efficiency[h,u,p,next(first(TESindex[h,p]),TESindex[h,p])]*TES_Mass[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])])*dt[p]
- (TES_mf_cold[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])])*dt[p]; 																			#kg

#-Top
subject to TES_MB_c3{h in House,u in (UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]),p in Period,t in Time[p] diff {last(Time[p])} }:
(TES_Mass[h,u,p,t+1,last(TESindex[h,p])] - TES_Mass[h,u,p,t,last(TESindex[h,p])]) = 
+ (TES_mf_cold[h,u,p,t,last(TESindex[h,p])])*dt[p] 
- (TES_efficiency[h,u,p,last(TESindex[h,p])]*TES_Mass[h,u,p,t,last(TESindex[h,p])] + TES_mf_hot[h,u,p,t,last(TESindex[h,p])])*dt[p]; 				#kg

#-CYCLIC CONDITIONS
#-Middle
subject to TES_MB_cyclic1{h in House,u in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h],p in Period,t in {last(Time[p])},T in TESindex[h,p] diff {first(TESindex[h,p]),last(TESindex[h,p])} }:
(TES_Mass[h,u,p,first(Time[p]),T] - TES_Mass[h,u,p,t,T]) =  
+ (TES_mf_hot[h,u,p,t,next(T,TESindex[h,p])] + TES_mf_cold[h,u,p,t,T] + TES_efficiency[h,u,p,next(T,TESindex[h,p])]*TES_Mass[h,u,p,t,next(T,TESindex[h,p])])*dt[p]
- (TES_mf_hot[h,u,p,t,T] + TES_mf_cold[h,u,p,t,next(T,TESindex[h,p])] + TES_efficiency[h,u,p,T]*TES_Mass[h,u,p,t,T])*dt[p]; 						#kg

#-Bottom
subject to TES_MB_cyclic2{h in House,u in (UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]),p in Period,t in {last(Time[p])} }:
(TES_Mass[h,u,p,first(Time[p]),first(TESindex[h,p])] - TES_Mass[h,u,p,t,first(TESindex[h,p])]) =  
+ (TES_mf_hot[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])] + TES_efficiency[h,u,p,next(first(TESindex[h,p]),TESindex[h,p])]*TES_Mass[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])])*dt[p]
- (TES_mf_cold[h,u,p,t,next(first(TESindex[h,p]),TESindex[h,p])])*dt[p]; 																			#kg

#-Top
subject to TES_MB_cyclic3{h in House,u in (UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]),p in Period,t in {last(Time[p])} }:
(TES_Mass[h,u,p,first(Time[p]),last(TESindex[h,p])] - TES_Mass[h,u,p,t,last(TESindex[h,p])]) = 
+ (TES_mf_cold[h,u,p,t,last(TESindex[h,p])])*dt[p] 
- (TES_efficiency[h,u,p,last(TESindex[h,p])]*TES_Mass[h,u,p,t,last(TESindex[h,p])] + TES_mf_hot[h,u,p,t,last(TESindex[h,p])])*dt[p]; 				#kg
