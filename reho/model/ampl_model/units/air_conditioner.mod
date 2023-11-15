######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---AIR-AIR HEAT PUMP MODEL 
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static air-air heat chiller for cooling including:
#	1. unit size depending on the maximal power input (i.e. compresor size)
#	2. temperature discrete output
#-References : 
#	-Source: Hoval SRM 14
# ----------------------------------------- PARAMETERS ---------------------------------------	
#-TEMPERATURE DISCRETIZATION
#-T_INDEX
#---------------------------------------------------------------------#
set AC_Tsupply default {13,15,18};																#deg C
param T_source_cool{u in UnitsOfType['Air_Conditioner'], p in Period,t in Time[p]};

#-T_HOT
#---------------------------------------------------------------------#
set AC_Tsink default {13,15,18};																		#deg C
param AC_Tsink_high{h in House,p in Period,t in Time[p],T in AC_Tsupply} :=  					#deg C
	if max{Th in AC_Tsink} Th <= T then
		max{Th in AC_Tsink} Th
	else
		min{Th in AC_Tsink: Th >= T} Th
	;
param AC_Tsink_low{h in House,p in Period,t in Time[p],T in AC_Tsupply} := 						#deg C
	if min{Th in AC_Tsink} Th >= T then
		min{Th in AC_Tsink} Th
	else
		max{Th in AC_Tsink: Th < T} Th
	;

#-T_COLD
#---------------------------------------------------------------------#
set AC_Tsource default {20,25,30,35,40,45};														#deg C
param AC_Tsource_high{u in UnitsOfType['Air_Conditioner'],p in Period,t in Time[p]} := 													#deg C
	if max{Tc in AC_Tsource} Tc <= T_source_cool[u,p,t] then
		max{Tc in AC_Tsource} Tc
	else
		min{Tc in AC_Tsource: Tc >= T_source_cool[u,p,t]} Tc
	;
param AC_Tsource_low{u in UnitsOfType['Air_Conditioner'],p in Period,t in Time[p]} := 														#deg C
	if min{Tc in AC_Tsource} Tc >= T_source_cool[u,p,t] then
		min{Tc in AC_Tsource} Tc
	else
		max{Tc in AC_Tsource: Tc < T_source_cool[u,p,t]} Tc
	;

#-Exergetic efficiency
#---------------------------------------------------------------------#
param AC_Eta_nominal{u in UnitsOfType['Air_Conditioner'],Th in AC_Tsink,Tc in AC_Tsource} default 0.3;		#-

param AC_Eta_low{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
		AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]]
	else
		AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]] +
		(T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t]);
	;
	
param AC_Eta_high{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
		AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]]
	else	
		AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]] +
		(T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t]);
	;
	
param AC_Eta{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsink_high[h,p,t,T] == AC_Tsink_low[h,p,t,T] then
		AC_Eta_low[h,u,p,t,T]
	else		
		AC_Eta_low[h,u,p,t,T] +
		(T - AC_Tsink_low[h,p,t,T])*(AC_Eta_high[h,u,p,t,T]-AC_Eta_low[h,u,p,t,T])/(AC_Tsink_high[h,p,t,T]-AC_Tsink_low[h,p,t,T])
	;

	
#-Power	consumption ratio
#---------------------------------------------------------------------#
param AC_Pmax_nominal{u in UnitsOfType['Air_Conditioner'],Th in AC_Tsink,Tc in AC_Tsource} default 1.00;		#-

param AC_Pmax_low{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
		AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]]
	else
		AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]] +
		(T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t])
	;
	
param AC_Pmax_high{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
		AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]]
	else
		AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]] +
		(T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t])
	;
	
param AC_Pmax{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if AC_Tsink_high[h,p,t,T] == AC_Tsink_low[h,p,t,T] then
		AC_Pmax_low[h,u,p,t,T]
	else		
		AC_Pmax_low[h,u,p,t,T] +
		(T - AC_Tsink_low[h,p,t,T])*(AC_Pmax_high[h,u,p,t,T]-AC_Pmax_low[h,u,p,t,T])/(AC_Tsink_high[h,p,t,T]-AC_Tsink_low[h,p,t,T])
	;


#-COP			
#---------------------------------------------------------------------#
param AC_COP{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
	if T < T_source_cool[u,p,t] and AC_Eta[h,u,p,t,T]*(T+273.15)/(T_source_cool[u,p,t]-T) < max{Tc in AC_Tsource}( AC_Eta_nominal[u,T,Tc]*(T+273.15)/(Tc-T) )	then
		AC_Eta[h,u,p,t,T]*(T+273.15)/(T_source_cool[u,p,t]-T)
	else
		max{Tc in AC_Tsource}( AC_Eta_nominal[u,T,Tc]*(T+273.15)/(Tc-T) )
	;	
	#-

#-GENERAL DATA
#-Part-load
#---------------------------------------------------------------------#
param AC_partload_max{u in UnitsOfType['Air_Conditioner']} default 1.0;		#-

# ----------------------------------------- VARIABLES ---------------------------------------
var AC_E_cooling{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} >= 0,<= Units_Fmax[u]*AC_COP[h,u,p,t,T];	#kW

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-Cooling
subject to AC_EB_c1{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in AC_Tsupply: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = AC_COP[h,u,p,t,T]*AC_E_cooling[h,u,p,t,T]; 									#kW

#--Totals
#-Attention! This is an averaged power consumption value over the whole operation set
subject to AC_c1{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = sum{T in AC_Tsupply}(AC_E_cooling[h,u,p,t,T]);												#kW

#-Minimum PartLoad
subject to AC_c2{h in House,u in UnitsOfType['Air_Conditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in AC_Tsupply} (AC_E_cooling[h,u,p,t,T]/AC_Pmax[h,u,p,t,T]) <= Units_Mult[u]*AC_partload_max[u];						#kW

subject to AC_c3{h in House,u in {'Air_Conditioner_DHN_'&h},p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = Units_demand['Electricity',u,p,t] + sum{st in StreamsOfUnit[u],T in AC_Tsupply: T = Streams_Tin[st,p,t]}AC_COP[h,u,p,t,T]*AC_E_cooling[h,u,p,t,T];												#kW

#-----------------------------------------------------------------------------------------------------------------------

