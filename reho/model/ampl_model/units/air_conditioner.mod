########################################################################################################
# Air-Air Heat Pump Model
#------------------------------------------------------------------------------------------------------#
# This model defines the parameters, variables, and constraints for an air-air heat pump system.
# It includes temperature indices, efficiency calculations, power consumption ratios, and constraints
# governing the operation of the heat pump.
########################################################################################################

#------------------------------------ Temperature Index Sets ------------------------------------------#

set AC_Tsupply default {13, 15, 18};  # Supply temperature in degrees Celsius
set AC_Tsink default {13, 15, 18};    # Heat sink temperature in degrees Celsius
set AC_Tsource default {20, 25, 30, 35, 40, 45};  # Heat source temperature in degrees Celsius

#------------------------------------ Temperature Parameters -----------------------------------------#

param T_source_cool{u in UnitsOfType['AirConditioner'], p in Period, t in Time[p]};

# Defining high and low sink temperatures based on supply temperature
param AC_Tsink_high{h in House, p in Period, t in Time[p], T in AC_Tsupply} :=
    if max{Th in AC_Tsink} Th <= T then
        max{Th in AC_Tsink} Th
    else
        min{Th in AC_Tsink: Th >= T} Th;

param AC_Tsink_low{h in House, p in Period, t in Time[p], T in AC_Tsupply} :=
    if min{Th in AC_Tsink} Th >= T then
        min{Th in AC_Tsink} Th
    else
        max{Th in AC_Tsink: Th < T} Th;

# Defining high and low source temperatures based on source cooling temperature
param AC_Tsource_high{u in UnitsOfType['AirConditioner'], p in Period, t in Time[p]} :=
    if max{Tc in AC_Tsource} Tc <= T_source_cool[u,p,t] then
        max{Tc in AC_Tsource} Tc
    else
        min{Tc in AC_Tsource: Tc >= T_source_cool[u,p,t]} Tc;

param AC_Tsource_low{u in UnitsOfType['AirConditioner'], p in Period, t in Time[p]} :=
    if min{Tc in AC_Tsource} Tc >= T_source_cool[u,p,t] then
        min{Tc in AC_Tsource} Tc
    else
        max{Tc in AC_Tsource: Tc < T_source_cool[u,p,t]} Tc;

#-------------------------------- Exergetic Efficiency Parameters ------------------------------------#

param AC_Eta_nominal{u in UnitsOfType['AirConditioner'], Th in AC_Tsink, Tc in AC_Tsource} default 0.3;

# Defining efficiency at low and high temperatures
param AC_Eta_low{h in House, u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in AC_Tsupply} :=
    if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
        AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]]
    else
        AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]] +
        (T_source_cool[u,p,t]-AC_Tsource_low[u,p,t]) *
        (AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_high[u,p,t]] - AC_Eta_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]]) /
        (AC_Tsource_high[u,p,t] - AC_Tsource_low[u,p,t]);

param AC_Eta_high{h in House, u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in AC_Tsupply} :=
    if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
        AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]]
    else
        AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]] +
        (T_source_cool[u,p,t]-AC_Tsource_low[u,p,t]) *
        (AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_high[u,p,t]] - AC_Eta_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]]) /
        (AC_Tsource_high[u,p,t] - AC_Tsource_low[u,p,t]);

param AC_Eta{h in House, u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in AC_Tsupply} :=
    if AC_Tsink_high[h,p,t,T] == AC_Tsink_low[h,p,t,T] then
        AC_Eta_low[h,u,p,t,T]
    else
        AC_Eta_low[h,u,p,t,T] +
        (T - AC_Tsink_low[h,p,t,T]) *
        (AC_Eta_high[h,u,p,t,T] - AC_Eta_low[h,u,p,t,T]) /
        (AC_Tsink_high[h,p,t,T] - AC_Tsink_low[h,p,t,T]);

#-------------------------------- Power Consumption Parameters --------------------------------------#

param AC_Pmax_nominal{u in UnitsOfType['AirConditioner'], Th in AC_Tsink, Tc in AC_Tsource} default 1.00;

param AC_Pmax_low{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
    if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
        AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]]
    else
        AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]] +
        (T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Pmax_nominal[u,AC_Tsink_low[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t]);
    
param AC_Pmax_high{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
    if AC_Tsource_high[u,p,t] == AC_Tsource_low[u,p,t] then
        AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]]
    else
        AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]] +
        (T_source_cool[u,p,t]-AC_Tsource_low[u,p,t])*(AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_high[u,p,t]]-AC_Pmax_nominal[u,AC_Tsink_high[h,p,t,T],AC_Tsource_low[u,p,t]])/(AC_Tsource_high[u,p,t]-AC_Tsource_low[u,p,t])
    ;
    
param AC_Pmax{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} :=
    if AC_Tsink_high[h,p,t,T] == AC_Tsink_low[h,p,t,T] then
        AC_Pmax_low[h,u,p,t,T]
    else        
        AC_Pmax_low[h,u,p,t,T] +
        (T - AC_Tsink_low[h,p,t,T])*(AC_Pmax_high[h,u,p,t,T]-AC_Pmax_low[h,u,p,t,T])/(AC_Tsink_high[h,p,t,T]-AC_Tsink_low[h,p,t,T]);

#-------------------------------- Coefficient of Performance (COP) ----------------------------------#

param AC_COP{h in House, u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in AC_Tsupply} :=
    if T < T_source_cool[u,p,t] and AC_Eta[h,u,p,t,T]*(T+273.15)/(T_source_cool[u,p,t]-T) < max{Tc in AC_Tsource} ( AC_Eta_nominal[u,T,Tc]*(T+273.15)/(Tc-T) ) then
        AC_Eta[h,u,p,t,T] * (T+273.15) / (T_source_cool[u,p,t]-T)
    else
        max{Tc in AC_Tsource} ( AC_Eta_nominal[u,T,Tc] * (T+273.15) / (Tc-T) );

#-------------------------------- Constraints and Energy Balances ----------------------------------#

var AC_Power{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in AC_Tsupply} >= 0,<= Units_Fmax[u]*AC_COP[h,u,p,t,T];

# Cooling output
subject to AC_energy_balance{h in House, u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h], st in StreamsOfUnit[u], p in Period, t in Time[p], T in AC_Tsupply: T = Streams_Tin[st,p,t]}:
    sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = AC_COP[h,u,p,t,T] * AC_Power[h,u,p,t,T];

# Power input
subject to AC_power_input{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = sum{T in AC_Tsupply} AC_Power[h,u,p,t,T];

# Sizing
subject to AC_sizing{h in House,u in UnitsOfType['AirConditioner'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
	sum{T in AC_Tsupply} (AC_Power[h,u,p,t,T]/AC_Pmax[h,u,p,t,T]) <= Units_Mult[u];
