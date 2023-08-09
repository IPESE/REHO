######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---DHW TANK MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-First-order buffer tank model including:
#	1. dis-/charging efficiencies 
#	2. self-discharging efficiency 
#	3. Temperature discretization (variable mass)
#-Definitions :
#	1. losses -> mass leaving T to T-1, here (mass) from point of view of T
#	2. cold stream from T-1 to T -> heat (mass) incoming to the slice T, here from point of view of T
#-References : 
# [1]	J. Rager, PhD Thesis, 2015.
# -------------------------------------------- SETS ------------------------------------------
param DHW_T_min := 10;																	#deg C
param DHW_T_max := 60;																	#deg C
param DHW_dT 	:= 50;																	#deg C

set DHWindex ordered by Reals 	  := {DHW_T_min .. DHW_T_max by DHW_dT};				#deg C

# ----------------------------------------- PARAMETERS ---------------------------------------
param DHW_flowrate{h in House, p in Period, t in Time[p]} >= 0 default 0;				#L/h		input data
param DHW_diameter{UnitsOfType['WaterTankDHW']}>=0 default 0.7;							#m			estimated														
param DHW_U_h{UnitsOfType['WaterTankDHW']}>=0 default 0.0013;							#kW/m2 K	[1]
param DHW_eff_ch{UnitsOfType['WaterTankDHW']}>=0 default 0.95;							#-			estimated
param DHW_efficiency{u in UnitsOfType['WaterTankDHW'],T in DHWindex diff {first(DHWindex)}} := 
	4*DHW_U_h[u]*(T-DHW_T_min)*3600/(cp_water_kj*DHW_diameter[u]*rho_water*DHW_dT);	#-

# ----------------------------------------- VARIABLES ---------------------------------------
var DHW_Mass{u in UnitsOfType['WaterTankDHW'],T in DHWindex,p in Period,t in Time[p]} 								>= 0,<= 1e2*sum{h in House}(ERA[h]);	#kg
var DHW_mf_cold{u in UnitsOfType['WaterTankDHW'],T in DHWindex diff {first(DHWindex)},p in Period,t in Time[p]} 	>= 0,<= sum{h in House}(ERA[h]);		#kg/h

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-STREAMS
subject to DHW_EB_c1{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h],T in DHWindex diff {first(DHWindex)},st in StreamsOfUnit[u],p in Period,t in Time[p]: T = Streams_Tout[st,p,t] and Streams_Hin[st] = 0}:
DHW_mf_cold[u,T,p,t] = (DHW_eff_ch[u])*(sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p]*3600/(cp_water_kj*DHW_dT);	#kg

#-ENERGY BALANCES
#-Middle
subject to DHW_MB_c1{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h],T in DHWindex diff {first(DHWindex),last(DHWindex)},p in Period,t in Time[p] diff {last(Time[p])} }:		
(DHW_Mass[u,T,p,next(t,Time[p])] - DHW_Mass[u,T,p,t]) =  
+ (DHW_mf_cold[u,T,p,t] + DHW_efficiency[u,next(T,DHWindex)]*DHW_Mass[u,next(T,DHWindex),p,t])*dt[p]
- (DHW_mf_cold[u,next(T,DHWindex),p,t] + DHW_efficiency[u,T]*DHW_Mass[u,T,p,t])*dt[p]; 											#kg

#-Bottom
subject to DHW_MB_c2{h in House,u in (UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]),p in Period,t in Time[p] diff {last(Time[p])}}:
(DHW_Mass[u,first(DHWindex),p,next(t,Time[p])] - DHW_Mass[u,first(DHWindex),p,t]) =  
+ (DHW_efficiency[u,next(first(DHWindex),DHWindex)]*DHW_Mass[u,next(first(DHWindex),DHWindex),p,t] + DHW_flowrate[h,p,t])*dt[p] 
- (DHW_mf_cold[u,next(first(DHWindex),DHWindex),p,t])*dt[p];																	#kg

#-Top
subject to DHW_MB_c3{h in House,u in (UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]),p in Period,t in Time[p] diff {last(Time[p])}}:
(DHW_Mass[u,last(DHWindex),p,next(t,Time[p])] - DHW_Mass[u,last(DHWindex),p,t]) = 
+ (DHW_mf_cold[u,last(DHWindex),p,t])*dt[p]
- (DHW_flowrate[h,p,t] + DHW_efficiency[u,last(DHWindex)]*DHW_Mass[u,last(DHWindex),p,t])*dt[p]; 								#kg

#--SIZING (SIA 385/2)
subject to DHW_c1{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_Mult[u] = 1.25*(1/rho_water)*sum{T in DHWindex} DHW_Mass[u,T,p,t];														#m3

subject to DHW_c2{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]}:
Units_Mult[u]/(1.25*(1/rho_water)) >= 1.05*(max{ip in Period,it in Time[ip]} (DHW_flowrate[h,ip,it]));							#kg

subject to DHW_c3{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]}:
Units_Mult[u] <= max{p in PeriodStandard} (sum{t in Time[p]} DHW_flowrate[h,p,t]/rho_water);									#m3

#subject to DHW_c4{h in House,u in (UnitsOfType['ElectricalHeater'] inter UnitsOfService['DHW']) inter UnitsOfHouse[h]}:	# enforces minimum ElectricalHeater size for dhw tank
#Units_Mult[u] >= (cp_water_kj/3600)*(max{p in Period,t in Time[p]} DHW_flowrate[h,p,t])*(DHW_T_max-DHW_T_min);					#kW

subject to DHW_c5{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
DHW_Mass[u,last(DHWindex),p,t] >= max{ip in Period,it in Time[ip]} (DHW_flowrate[h,ip,it]);										#kg

#-CYCLIC CONDITIONS
#-Middle
subject to DHW_MB_cyclic1{h in House,u in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h],T in DHWindex diff {first(DHWindex),last(DHWindex)},p in Period,t in {last(Time[p])} }:
(DHW_Mass[u,T,p,first(Time[p])] - DHW_Mass[u,T,p,t]) =  
+ (DHW_mf_cold[u,T,p,t] + DHW_efficiency[u,next(T,DHWindex)]*DHW_Mass[u,next(T,DHWindex),p,t])*dt[p]
- (DHW_mf_cold[u,next(T,DHWindex),p,t] + DHW_efficiency[u,T]*DHW_Mass[u,T,p,t])*dt[p]; 											#kg

#-Bottom
subject to DHW_MB_cyclic2{h in House,u in (UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]),p in Period,t in {last(Time[p])} }:
(DHW_Mass[u,first(DHWindex),p,first(Time[p])] - DHW_Mass[u,first(DHWindex),p,t]) =  
+ (DHW_efficiency[u,next(first(DHWindex),DHWindex)]*DHW_Mass[u,next(first(DHWindex),DHWindex),p,t] + DHW_flowrate[h,p,t])*dt[p] 
- (DHW_mf_cold[u,next(first(DHWindex),DHWindex),p,t])*dt[p];																	#kg

#-Top
subject to DHW_MB_cyclic3{h in House,u in (UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]),p in Period ,t in {last(Time[p])}}:
(DHW_Mass[u,last(DHWindex),p,first(Time[p])] - DHW_Mass[u,last(DHWindex),p,t]) = 
+ (DHW_mf_cold[u,last(DHWindex),p,t])*dt[p]
- (DHW_flowrate[h,p,t] + DHW_efficiency[u,last(DHWindex)]*DHW_Mass[u,last(DHWindex),p,t])*dt[p]; 								#kg
								
#-----------------------------------------------------------------------------------------------------------------------	


