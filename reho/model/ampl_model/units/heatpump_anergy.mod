######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ANERGY HEAT PUMP MODEL (work in progress)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static air-water heat pump model including:
#	1. unit size depending on the maximal power input (i.e. compresor size)
#	2. temperature discrete output
#-References : 
#-Source: Hoval Belaria IR9
# ----------------------------------------- PARAMETERS ---------------------------------------
#-TEMPERATURE DISCRETIZATION
#-T_INDEX
#---------------------------------------------------------------------#
set WHP_Tsupply default {35,45,55};																	#-
set WHPindex_demand default {14};																		#-
# set WHPindex_demand default {10,12,14,16,18,20,22,24,26,28};											#-
param Costs_CO2{WHPindex_demand} default 0.05;															#CHF/kWh

#-T_HOT
#---------------------------------------------------------------------#
set WHP_Tsink default {35,45,55};																	#deg C
param WHP_Tsink_high{h in House,p in Period,t in Time[p],T in WHP_Tsupply} :=  						#deg C
	if max{Th in WHP_Tsink} Th <= T then
		max{Th in WHP_Tsink} Th
	else
		min{Th in WHP_Tsink: Th >= T} Th
	;
param WHP_Tsink_low{h in House,p in Period,t in Time[p],T in WHP_Tsupply} := 						#deg C
	if min{Th in WHP_Tsink} Th >= T then
		min{Th in WHP_Tsink} Th
	else
		max{Th in WHP_Tsink: Th < T} Th
	;

#-T_COLD
#---------------------------------------------------------------------#
set WHP_Tsource default {-5,0,5,10,15,20,25};														#deg C
param WHP_Tsource_high{p in Period,t in Time[p],T in WHPindex_demand} := 								#deg C
	if max{Tc in WHP_Tsource} Tc <= T then
		max{Tc in WHP_Tsource} Tc
	else
		min{Tc in WHP_Tsource: Tc >= T} Tc
	;
param WHP_Tsource_low{p in Period,t in Time[p],T in WHPindex_demand} := 									#deg C
	if min{Tc in WHP_Tsource} Tc >= T then
		min{Tc in WHP_Tsource} Tc
	else
		max{Tc in WHP_Tsource: Tc < T} Tc
	;

#-Exergetic efficiency
#---------------------------------------------------------------------#
param WHP_Eta_nominal{u in UnitsOfType['HeatPump_anergy'],Th in WHP_Tsink,Tc in WHP_Tsource} default 0.3;		#-

#-Source (co2) interpolation for lower sink
param WHP_Eta_low{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsource_high[p,t,Tc] == WHP_Tsource_low[p,t,Tc] then
		WHP_Eta_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]]
	else
		WHP_Eta_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]] +
		(Tc-WHP_Tsource_low[p,t,Tc])*(WHP_Eta_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_high[p,t,Tc]]-WHP_Eta_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]])/(WHP_Tsource_high[p,t,Tc]-WHP_Tsource_low[p,t,Tc]);
	;
	
param WHP_Eta_high{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsource_high[p,t,Tc] == WHP_Tsource_low[p,t,Tc] then
		WHP_Eta_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_low[p,t,Tc]]
	else
		WHP_Eta_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]] +
		(Tc-WHP_Tsource_low[p,t,Tc])*(WHP_Eta_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_high[p,t,Tc]]-WHP_Eta_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_low[p,t,Tc]])/(WHP_Tsource_high[p,t,Tc]-WHP_Tsource_low[p,t,Tc]);
	;
	
param WHP_Eta{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsink_high[h,p,t,Th] == WHP_Tsink_low[h,p,t,Th] then
		WHP_Eta_low[h,u,p,t,Th,Tc] 
	else		
		WHP_Eta_low[h,u,p,t,Th,Tc] +
		(Th - WHP_Tsink_low[h,p,t,Th])*(WHP_Eta_high[h,u,p,t,Th,Tc]-WHP_Eta_low[h,u,p,t,Th,Tc])/(WHP_Tsink_high[h,p,t,Th]-WHP_Tsink_low[h,p,t,Th])
	;

	
#-Power	consumption ratio
#---------------------------------------------------------------------#
param WHP_Pmax_nominal{u in UnitsOfType['HeatPump_anergy'],Th in WHP_Tsink,Tc in WHP_Tsource} default 1.00;		#-

param WHP_Pmax_low{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsource_high[p,t,Tc] == WHP_Tsource_low[p,t,Tc] then
		WHP_Pmax_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]]
	else
		WHP_Pmax_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]] +
		(Tc-WHP_Tsource_low[p,t,Tc])*(WHP_Pmax_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_high[p,t,Tc]]-WHP_Pmax_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]])/(WHP_Tsource_high[p,t,Tc]-WHP_Tsource_low[p,t,Tc]);
	;
	
param WHP_Pmax_high{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsource_high[p,t,Tc] == WHP_Tsource_low[p,t,Tc] then
		WHP_Pmax_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_low[p,t,Tc]]
	else
		WHP_Pmax_nominal[u,WHP_Tsink_low[h,p,t,Th],WHP_Tsource_low[p,t,Tc]] +
		(Tc-WHP_Tsource_low[p,t,Tc])*(WHP_Pmax_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_high[p,t,Tc]]-WHP_Pmax_nominal[u,WHP_Tsink_high[h,p,t,Th],WHP_Tsource_low[p,t,Tc]])/(WHP_Tsource_high[p,t,Tc]-WHP_Tsource_low[p,t,Tc]);
	;
	
param WHP_Pmax{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} :=
	if WHP_Tsink_high[h,p,t,Th] == WHP_Tsink_low[h,p,t,Th] then
		WHP_Pmax_low[h,u,p,t,Th,Tc] 
	else		
		WHP_Pmax_low[h,u,p,t,Th,Tc] +
		(Th - WHP_Tsink_low[h,p,t,Th])*(WHP_Pmax_high[h,u,p,t,Th,Tc]-WHP_Pmax_low[h,u,p,t,Th,Tc])/(WHP_Tsink_high[h,p,t,Th]-WHP_Tsink_low[h,p,t,Th])
	;

	
#-COP			
#---------------------------------------------------------------------#
param WHP_COP{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} := WHP_Eta[h,u,p,t,Th,Tc]*(Th+273.15)/(Th-Tc);


#-GENERAL DATA
#-Part-load
#---------------------------------------------------------------------#
param WHP_partload_max{u in UnitsOfType['HeatPump_anergy']} default 1.0;		#-
  
# ----------------------------------------- VARIABLES ---------------------------------------
var WHP_E_heating{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand} >= 0,<= Units_Fmax[u]*20;	#kW
var WHP_y_heating{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,Tc in WHPindex_demand} binary;											#-

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-Heating
subject to WHP_EB_c1{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],Th in WHP_Tsupply: Th = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = sum{Tc in WHPindex_demand}(WHP_COP[h,u,p,t,Th,Tc]*WHP_E_heating[h,u,p,t,Th,Tc]); 		#kW

subject to WHP_EB_c2{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0; 																#kW

subject to WHP_EB_c3{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p],Th in WHP_Tsupply,Tc in WHPindex_demand}:
WHP_E_heating[h,u,p,t,Th,Tc] <= 100*WHP_y_heating[h,u,p,Tc] ; 																								#kW

subject to WHP_EB_c4{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period}:
sum{Tc in WHPindex_demand} WHP_y_heating[h,u,p,Tc] = 1; 																									#-

#--Totals
#-Attention! This is an averaged power consumption value over the whole operation set
subject to WHP_c1{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = sum{Th in WHP_Tsupply,Tc in WHPindex_demand}(WHP_E_heating[h,u,p,t,Th,Tc]);										#kW

#--Sizing 
subject to WHP_c2{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{Th in WHP_Tsupply,Tc in WHPindex_demand} (WHP_E_heating[h,u,p,t,Th,Tc]/WHP_Pmax[h,u,p,t,Th,Tc]) <= Units_Mult[u]*WHP_partload_max[u];				#kW

#--Cooling
subject to WHP_cooling_c1{h in House,u in UnitsOfType['HeatPump_anergy'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st]=0}:
sum{se in ServicesOfStream[st]}(Streams_Q[se,st,p,t]) <= Units_Use[u]*1e3;																					#kW



#-----------------------------------------------------------------------------------------------------------------------
















