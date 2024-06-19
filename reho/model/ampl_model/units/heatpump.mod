######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Heatpump with air, water, or geothermal heat source
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-Static heat pump model including:
#	1. unit size depending on the maximal power input (i.e. compressor size)
#	2. temperature discrete output
#-References : 
# [1]	Hoval Belaria IR9

#-T_INDEX
param T_source{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]};

#-T_HOT
set HP_Tsink default {35,45,55};																	#deg C
param HP_Tsink_high{h in House,p in Period,t in Time[p],T in HP_Tsupply} :=  						#deg C
	if max{Th in HP_Tsink} Th <= T then
		max{Th in HP_Tsink} Th
	else
		min{Th in HP_Tsink: Th >= T} Th
	;
param HP_Tsink_low{h in House,p in Period,t in Time[p],T in HP_Tsupply} := 						#deg C
	if min{Th in HP_Tsink} Th >= T then
		min{Th in HP_Tsink} Th
	else
		max{Th in HP_Tsink: Th < T} Th
	;

#-T_COLD
set HP_Tsource default {-20,-15,-10,-7,-2,2,7,10,15,20};											#deg C
param HP_Tsource_high{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]} := 														#deg C
	if max{Tc in HP_Tsource} Tc <= T_source[u,p,t] then
		max{Tc in HP_Tsource} Tc
	else
		min{Tc in HP_Tsource: Tc >= T_source[u,p,t]} Tc
	;
param HP_Tsource_low{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]} := 														#deg C
	if min{Tc in HP_Tsource} Tc >= T_source[u,p,t] then
		min{Tc in HP_Tsource} Tc
	else
		max{Tc in HP_Tsource: Tc < T_source[u,p,t]} Tc
	;

#-Exergetic efficiency
param HP_Eta_nominal{u in UnitsOfType['HeatPump'],Th in HP_Tsink,Tc in HP_Tsource} default 0.3;		#-

param HP_Eta_low{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	;
	
param HP_Eta_high{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]]
	else	
		HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	;
	
param HP_Eta{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[h,p,t,T] == HP_Tsink_low[h,p,t,T] then
		HP_Eta_low[h,u,p,t,T]
	else		
		HP_Eta_low[h,u,p,t,T] +
		(T - HP_Tsink_low[h,p,t,T])*(HP_Eta_high[h,u,p,t,T]-HP_Eta_low[h,u,p,t,T])/(HP_Tsink_high[h,p,t,T]-HP_Tsink_low[h,p,t,T])
	;

	
#-Power	consumption ratio
param HP_Pmax_nominal{u in UnitsOfType['HeatPump'],Th in HP_Tsink,Tc in HP_Tsource} default 1.00;		#-

param HP_Pmax_low{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t])
	;
	
param HP_Pmax_high{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t])
	;
	
param HP_Pmax{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[h,p,t,T] == HP_Tsink_low[h,p,t,T] then
		HP_Pmax_low[h,u,p,t,T]
	else		
		HP_Pmax_low[h,u,p,t,T] +
		(T - HP_Tsink_low[h,p,t,T])*(HP_Pmax_high[h,u,p,t,T]-HP_Pmax_low[h,u,p,t,T])/(HP_Tsink_high[h,p,t,T]-HP_Tsink_low[h,p,t,T])
	;

#-COP
param HP_COP{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source[u,p,t] and HP_Eta[h,u,p,t,T]*(T+273.15)/(T_source[u,p,t]-T) < max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta[h,u,p,t,T]*(T+273.15)/(T-T_source[u,p,t])
	else
		max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )
	;	
	#-

#-GENERAL DATA
#-Part-load
param HP_partload_max{u in UnitsOfType['HeatPump']} default 1.0;		#-
  
var HP_E_heating{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} >= 0,<= Units_Fmax[u]*HP_COP[h,u,p,t,T];

#-Heating
subject to HP_energy_balance{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in HP_Tsupply: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = HP_COP[h,u,p,t,T]*HP_E_heating[h,u,p,t,T];

subject to HP_EB_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0;

#--Totals
#-Attention! This is an averaged power consumption value over the whole operation set
subject to HP_c1{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply}(HP_E_heating[h,u,p,t,T]);

#--Sizing 
subject to HP_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in HP_Tsupply} (HP_E_heating[h,u,p,t,T]/HP_Pmax[h,u,p,t,T]) <= Units_Mult[u]*HP_partload_max[u];

#-Need of technical buffer tank (defrost & hydraulic decoupling) if no floor heating & cycle inversion
subject to HP_c4{h in House,ui in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
Units_Mult[uj] >= if Th_supply_0[h] > 50 then 0.015*Units_Mult[ui]*HP_Eta_nominal[ui,35,20]*(35+273.15)/(35 - (20)) else 0;			#m3

param DHN_CO2_efficiency default 0.95; # The Innovative Concept of Cold District Heating Networks: A Literature Review, Marco Pellegrini
subject to DHN_heat{h in House, u in {'HeatPump_DHN_'&h}, p in Period, t in Time[p]}:
Units_demand['Heat',u,p,t]*DHN_CO2_efficiency = sum{st in StreamsOfUnit[u], se in ServicesOfStream[st]} Streams_Q[se,st,p,t] - sum{st in StreamsOfUnit[u], T in HP_Tsupply: T = Streams_Tin[st,p,t]} HP_E_heating[h,u,p,t,T];

subject to enforce_DHN{h in House, u in {'DHN_hex_in_'&h}, v in {'HeatPump_DHN_'&h}}:
0.95 * sum{p in PeriodStandard, t in Time[p]}(House_Q_heating[h,p,t]* dp[p] * dt[p]) <= sum{p in PeriodStandard, t in Time[p]} (Units_demand['Heat',u,p,t]  * dp[p] * dt[p] + sum{st in StreamsOfUnit[v], se in ServicesOfStream[st]} (Streams_Q[se,st,p,t] * dp[p] * dt[p]));

#--Only one type of heat pump per house
subject to max_one_HeatPump_per_house{h in House}:
sum{u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]} Units_Use[u] <= 1;
