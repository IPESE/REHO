######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Heatpump with air, water, or geothermal heat source (district)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-T_INDEX
param T_source{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]} default 8;
set HP_Tsupply default {80};																	#-

#-T_HOT
set HP_Tsink default {60};																	#deg C
param HP_Tsink_high{p in Period,t in Time[p],T in HP_Tsupply} :=  						#deg C
	if max{Th in HP_Tsink} Th <= T then
		max{Th in HP_Tsink} Th
	else
		min{Th in HP_Tsink: Th >= T} Th
	;
param HP_Tsink_low{p in Period,t in Time[p],T in HP_Tsupply} := 						#deg C
	if min{Th in HP_Tsink} Th >= T then
		min{Th in HP_Tsink} Th
	else
		max{Th in HP_Tsink: Th < T} Th
	;

#-T_COLD
set HP_Tsource default {-20,-15,-10,-7,-2,2,7,9};											#deg C
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

param HP_Eta_low{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	;
	
param HP_Eta_high{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]]
	else	
		HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	;
	
param HP_Eta{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[p,t,T] == HP_Tsink_low[p,t,T] then
		HP_Eta_low[u,p,t,T]
	else		
		HP_Eta_low[u,p,t,T] +
		(T - HP_Tsink_low[p,t,T])*(HP_Eta_high[u,p,t,T]-HP_Eta_low[u,p,t,T])/(HP_Tsink_high[p,t,T]-HP_Tsink_low[p,t,T])
	;

	
#-Power	consumption ratio
param HP_Pmax_nominal{u in UnitsOfType['HeatPump'],Th in HP_Tsink,Tc in HP_Tsource} default 1.00;		#-

param HP_Pmax_low{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t])
	;
	
param HP_Pmax_high{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t])
	;
	
param HP_Pmax{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[p,t,T] == HP_Tsink_low[p,t,T] then
		HP_Pmax_low[u,p,t,T]
	else		
		HP_Pmax_low[u,p,t,T] +
		(T - HP_Tsink_low[p,t,T])*(HP_Pmax_high[u,p,t,T]-HP_Pmax_low[u,p,t,T])/(HP_Tsink_high[p,t,T]-HP_Tsink_low[p,t,T])
	;

#-COP
param HP_COP{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source[u,p,t] and HP_Eta[u,p,t,T]*(T+273.15)/(T_source[u,p,t]-T) < max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta[u,p,t,T]*(T+273.15)/(T-T_source[u,p,t])
	else
		max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )
	;	
	#-

#-GENERAL DATA
#-Part-load
param HP_partload_max{u in UnitsOfType['HeatPump']} default 1.0;		#-
  
var HP_E_heating{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} >= 0,<= Units_Fmax[u]*HP_COP[u,p,t,T];

#-Heating
subject to HP_energy_balance{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = sum{T in HP_Tsupply} HP_COP[u,p,t,T]*HP_E_heating[u,p,t,T];

#subject to HP_EB_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
#sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0;

#--Totals
#-Attention! This is an averaged power consumption value over the whole operation set
subject to HP_c1{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply} HP_E_heating[u,p,t,T];

#--Sizing 
subject to HP_c2{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
sum{T in HP_Tsupply} (HP_E_heating[u,p,t,T]/HP_Pmax[u,p,t,T]) <= Units_Mult[u]*HP_partload_max[u];

#subject to DHN_heat{h in House, u in {'HeatPump_DHN_'&h}, p in Period, t in Time[p]}:
#Units_demand['Heat',u,p,t] = sum{st in StreamsOfUnit[u], se in ServicesOfStream[st]} Streams_Q[se,st,p,t] - sum{st in StreamsOfUnit[u], T in HP_Tsupply: T = Streams_Tin[st,p,t]} HP_E_heating[h,u,p,t,T];

# ----------------------------------------- HEX Direct Cooling ---------------------------------------

param DHN_efficiency_out{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]}  := if min{T in HP_Tsupply} T >= T_source[u,p,t] + 2 then 1.0 else 0;
param T_m{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]}  := min{T in HP_Tsupply} (T) - T_source[u,p,t];
param U_hex default 1; # [kW / m2K], https://sistemas.eel.usp.br/docentes/arquivos/5817712/LOQ4086/saari__heat_exchanger_dimensioning.pdf

subject to HEX_cooling1{u in UnitsOfType['HeatPump'], v in UnitsOfType['DHN_direct_cooling'], p in Period,t in Time[p]}:
	Units_demand['Heat',v,p,t]/(U_hex * T_m[u,p,t])  <= Units_Mult[v];	

subject to HEX_cooling3{u in UnitsOfType['HeatPump'], v in UnitsOfType['DHN_direct_cooling'], p in Period,t in Time[p]}:
	Units_demand['Heat',v,p,t] <= 1e4 *  DHN_efficiency_out[u,p,t];	
