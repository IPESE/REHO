######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Heat storage tank, with interperiod storage conversion
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param TES_IP_T_min{h in House,p in Period} default 20;																											#deg C															
param TES_IP_T_max{h in House,p in Period} := 60; #min{Thp in HP_Tsupply: Thp >= min( max{t in Time[p]} Th_supply[h,p,t], max{i in HP_Tsupply} i)} Thp;	#deg C
param TES_IP_T_ret{h in House,p in Period} := 35; #(T_comfort_min_0[h] + TES_IP_T_max[h,p]*(alpha_h[h]*Mcp_0h[h]))/(1+alpha_h[h]*Mcp_0h[h]);									#deg C

#Set the number of layer (size set) and their respective temperature. There are 2 different temperature here (Tmax at the top and T return)
set TESindex_IP{h in House,p in Period} ordered by Reals := {TES_IP_T_max[h,p],TES_IP_T_ret[h,p]};																	#deg C

param TES_IP_dT{h in House,p in Period,T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])} } := T - prev(T,TESindex_IP[h,p]);											#deg C

param TES_IP_diameter{UnitsOfType['WaterTankSH_interperiod']} default 0.98;		#m			Viessmann (mean from Vitocell E)
param TES_IP_U_h{UnitsOfType['WaterTankSH_interperiod']} 	default 0.0013;		#kW/m2 K	[1]
param TES_IP_eff_ch{UnitsOfType['WaterTankSH_interperiod']} 	default 0.99;		#-
param TES_IP_eff_di{UnitsOfType['WaterTankSH_interperiod']} 	default 0.99;		#-
param TES_IP_Tamb{UnitsOfType['WaterTankSH_interperiod']} 	default 20;			#degC		estimated
param TES_IP_efficiency{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h],p in Period,T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])} }:=
	4*TES_IP_U_h[u]*(T-TES_IP_Tamb[u])*3600/(cp_water_kj*TES_IP_diameter[u]*1000*rho_water*TES_IP_dT[h,p,T]);						#-
	
# overall energy capacity
var TES_IP_Mass{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year,TESindex_IP[h,PeriodOfYear[hy]]}>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg
# Flow entering (positive energy) a layer									>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg
var TES_IP_mf_cold{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])}}	>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg/h
# Flow leaving a layer
var TES_IP_mf_hot{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])}} 	>= 0,<= 1e4*sum{i in House}(ERA[i]);	#kg/h

#-SOC
subject to TES_IP_c1{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year}:
sum{T in TESindex_IP[h,PeriodOfYear[hy]]} TES_IP_Mass[h,u,hy,T] = rho_water*Units_Mult[u];														#kg

subject to TES_IP_c2{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year}:
sum{T in TESindex_IP[h,PeriodOfYear[hy]]}(T*TES_IP_Mass[h,u,hy,T]) >= if (T_ext[PeriodOfYear[hy],TimeOfYear[hy]] <= -70) then rho_water*Units_Mult[u]*Th_return[h,PeriodOfYear[hy],TimeOfYear[hy]] else rho_water*Units_Mult[u]*first(TESindex_IP[h,PeriodOfYear[hy]]);

#-CHARGING/DISCHARGING
subject to TES_IP_c3{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year,T in TESindex_IP[h,PeriodOfYear[hy]] diff {first(TESindex_IP[h,PeriodOfYear[hy]])} }:
TES_IP_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy],T]*dt[PeriodOfYear[hy]] <= TES_IP_Mass[h,u,hy,T];																		#kg																

subject to TES_IP_c4{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year,T in TESindex_IP[h,PeriodOfYear[hy]] diff {first(TESindex_IP[h,PeriodOfYear[hy]])} }:
TES_IP_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy],T]*dt[PeriodOfYear[hy]] <= TES_IP_Mass[h,u,hy,T];																			#kg

#-STREAMS
#-cold stream from T-1 to T -> heat (mass) incoming to the slice T, here from point of view of T
subject to TES_IP_energy_balance{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])}: Streams_Tout[st,p,t] = T and Streams_Hout[st] = 1}:
TES_IP_mf_cold[h,u,p,t,T] = (TES_IP_eff_ch[u])*(sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p]*3600/( cp_water_kj*TES_IP_dT[h,p,T] );		#kg

#-hot stream from T to T-1 -> heat (mass) leaving to the slice T, here from point of view of T
subject to TES_IP_EB_c2{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in TESindex_IP[h,p] diff {first(TESindex_IP[h,p])}: Streams_Tin[st,p,t] = T and Streams_Hin[st] = 1}:
TES_IP_mf_hot[h,u,p,t,T] = (1/TES_IP_eff_di[u])*(sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p]*3600/( cp_water_kj*TES_IP_dT[h,p,T] );		#kg

#-ENERGY BALANCES
#-Middle (can contain several layers)
# CAREFUL ! The temperature level cyclic condition can't work with TD with different temperature level. Should be improved.

subject to TES_IP_MB_c1{h in House,u in UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h], hy in Year,T in TESindex_IP[h,PeriodOfYear[hy]] diff {first(TESindex_IP[h,PeriodOfYear[hy]]),last(TESindex_IP[h,PeriodOfYear[hy]])} }:
(TES_IP_Mass[h,u,next(hy,Year),T] - TES_IP_Mass[h,u,hy,T]) =  
+ (TES_IP_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy],next(T,TESindex_IP[h,PeriodOfYear[hy]])] + TES_IP_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy],T] + TES_IP_efficiency[h,u,PeriodOfYear[hy],next(T,TESindex_IP[h,PeriodOfYear[hy]])]*TES_IP_Mass[h,u,hy,next(T,TESindex_IP[h,PeriodOfYear[hy]])])*dt[PeriodOfYear[hy]]
- (TES_IP_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy],T] + TES_IP_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy],next(T,TESindex_IP[h,PeriodOfYear[hy]])] + TES_IP_efficiency[h,u,PeriodOfYear[hy],T]*TES_IP_Mass[h,u,hy,T])*dt[PeriodOfYear[hy]]; 						#kg

#-Bottom
subject to TES_IP_MB_c2{h in House,u in (UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h]), hy in Year}:
(TES_IP_Mass[h,u,next(hy,Year),first(TESindex_IP[h,PeriodOfYear[next(hy,Year)]])] - TES_IP_Mass[h,u,hy,first(TESindex_IP[h,PeriodOfYear[hy]])]) =  
+ (TES_IP_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy],next(first(TESindex_IP[h,PeriodOfYear[hy]]),TESindex_IP[h,PeriodOfYear[hy]])] + TES_IP_efficiency[h,u,PeriodOfYear[hy],next(first(TESindex_IP[h,PeriodOfYear[hy]]),TESindex_IP[h,PeriodOfYear[hy]])]*TES_IP_Mass[h,u,hy,next(first(TESindex_IP[h,PeriodOfYear[hy]]),TESindex_IP[h,PeriodOfYear[hy]])])*dt[PeriodOfYear[hy]]
- (TES_IP_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy],next(first(TESindex_IP[h,PeriodOfYear[hy]]),TESindex_IP[h,PeriodOfYear[hy]])])*dt[PeriodOfYear[hy]]; 																			#kg

#-Top
subject to TES_IP_MB_c3{h in House,u in (UnitsOfType['WaterTankSH_interperiod'] inter UnitsOfHouse[h]), hy in Year}:
(TES_IP_Mass[h,u,next(hy,Year),last(TESindex_IP[h,PeriodOfYear[next(hy,Year)]])] - TES_IP_Mass[h,u,hy,last(TESindex_IP[h,PeriodOfYear[hy]])]) = 
+ (TES_IP_mf_cold[h,u,PeriodOfYear[hy],TimeOfYear[hy],last(TESindex_IP[h,PeriodOfYear[hy]])])*dt[PeriodOfYear[hy]] 
- (TES_IP_efficiency[h,u,PeriodOfYear[hy],last(TESindex_IP[h,PeriodOfYear[hy]])]*TES_IP_Mass[h,u,hy,last(TESindex_IP[h,PeriodOfYear[hy]])] + TES_IP_mf_hot[h,u,PeriodOfYear[hy],TimeOfYear[hy],last(TESindex_IP[h,PeriodOfYear[hy]])])*dt[PeriodOfYear[hy]]; 				#kg
