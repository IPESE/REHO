######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---AIR-WATER HEAT PUMP MODEL
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
param T_source{u in UnitsOfType['HeatPump'], p in Period,t in Time[p]} default 10;
#---------------------------------------------------------------------#
#-T_HOT
#---------------------------------------------------------------------#
#'''
#From what I understand so far, HP_Tsupply is defined in subproblem.mod as a set with {35,45,55} temperature values. 
#param HP_Tsink_high is trying to supply the closest available (that is equal to if not higher supply temperature from the HP). But since HP_Tsupply os same as HP_Tsink, 
#the greater tha condition is never evaluated.
#ß'''

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

/*
'''
This piece of code defines parameters for a heat pump sink temperatures in a house heating system model. The logic involves determining the appropriate high and low sink temperatures based on a given supply temperature. Here is a step-by-step explanation of each part:

### Setting Default Sink Temperatures
```text
set HP_Tsink default {35, 45, 55};  # deg C

- This line sets the default possible sink temperatures for the heat pump to 35°C, 45°C, and 55°C.

### High Sink Temperature Parameter
```text
param HP_Tsink_high{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=  # deg C
	if max{Th in HP_Tsink} Th <= T then
		max{Th in HP_Tsink} Th
	else
		min{Th in HP_Tsink: Th >= T} Th
	;

- **Purpose**: Determine the "high" sink temperature based on a given supply temperature `T`.
- **Logic**:
  1. **Check Condition**: `if max{Th in HP_Tsink} Th <= T`
     - If the maximum value in `HP_Tsink` (which is 55°C) is less than or equal to `T` (the given supply temperature):
       - Use the maximum value in `HP_Tsink`.
     - Otherwise:
       - Find the minimum value in `HP_Tsink` that is greater than or equal to `T`.
  2. **Example**:
     - If `T = 60°C`, then `max{Th in HP_Tsink} Th = 55°C`, which is less than `T`, so `HP_Tsink_high` would be 55°C.
     - If `T = 40°C`, the condition fails, so it finds the minimum value in `HP_Tsink` that is greater than or equal to 40°C, which is 45°C.

### Low Sink Temperature Parameter
```text
param HP_Tsink_low{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=  # deg C
	if min{Th in HP_Tsink} Th >= T then
		min{Th in HP_Tsink} Th
	else
		max{Th in HP_Tsink: Th < T} Th
	;
```
- **Purpose**: Determine the "low" sink temperature based on a given supply temperature `T`.
- **Logic**:
  1. **Check Condition**: `if min{Th in HP_Tsink} Th >= T`
     - If the minimum value in `HP_Tsink` (which is 35°C) is greater than or equal to `T`:
       - Use the minimum value in `HP_Tsink`.
     - Otherwise:
       - Find the maximum value in `HP_Tsink` that is less than `T`.
  2. **Example**:
     - If `T = 30°C`, then `min{Th in HP_Tsink} Th = 35°C`, which is greater than `T`, so `HP_Tsink_low` would be 35°C.
     - If `T = 40°C`, the condition fails, so it finds the maximum value in `HP_Tsink` that is less than 40°C, which is 35°C.

### Summary
- **`HP_Tsink_high`**: Finds the appropriate higher bound temperature. It’s either the highest temperature in `HP_Tsink` if it is less than or equal to `T`, or the smallest temperature in `HP_Tsink` that is still higher than or equal to `T`.
- **`HP_Tsink_low`**: Finds the appropriate lower bound temperature. It’s either the lowest temperature in `HP_Tsink` if it is greater than or equal to `T`, or the largest temperature in `HP_Tsink` that is still lower than `T`.

These parameters help ensure that the heat pump operates within efficient temperature ranges relative to the supply temperature `T`.
'''
*/

#-T_COLD
#---------------------------------------------------------------------#
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

/*

'''
This piece of code defines parameters for a heat pumps source temperatures, similar to how the sink temperatures were defined previously. The logic is about determining the appropriate high and low source temperatures based on a given source temperature. Heres the breakdown:

### Setting Default Source Temperatures
```text
set HP_Tsource default {-20, -15, -10, -7, -2, 2, 7, 10, 15, 20};  # deg C
```
- This line sets the default possible source temperatures for the heat pump to a range from -20°C to 20°C.

### High Source Temperature Parameter
```text
param HP_Tsource_high{u in UnitsOfType[HeatPump], p in Period, t in Time[p]} :=  # deg C
	if max{Tc in HP_Tsource} Tc <= T_source[u,p,t] then
		max{Tc in HP_Tsource} Tc
	else
		min{Tc in HP_Tsource: Tc >= T_source[u,p,t]} Tc
	;
```
- **Purpose**: Determine the "high" source temperature based on a given source temperature `T_source[u,p,t]`.
- **Logic**:
  1. **Check Condition**: `if max{Tc in HP_Tsource} Tc <= T_source[u,p,t]`
     - If the maximum value in `HP_Tsource` (which is 20°C) is less than or equal to `T_source[u,p,t]`:
       - Use the maximum value in `HP_Tsource`.
     - Otherwise:
       - Find the minimum value in `HP_Tsource` that is greater than or equal to `T_source[u,p,t]`.
  2. **Example**:
     - If `T_source[u,p,t] = 25°C`, then `max{Tc in HP_Tsource} Tc = 20°C`, which is less than `T_source[u,p,t]`, so `HP_Tsource_high` would be 20°C.
     - If `T_source[u,p,t] = 5°C`, the condition fails, so it finds the minimum value in `HP_Tsource` that is greater than or equal to 5°C, which is 7°C.

### Low Source Temperature Parameter
```text
param HP_Tsource_low{u in UnitsOfType[HeatPump], p in Period, t in Time[p]} :=  # deg C
	if min{Tc in HP_Tsource} Tc >= T_source[u,p,t] then
		min{Tc in HP_Tsource} Tc
	else
		max{Tc in HP_Tsource: Tc < T_source[u,p,t]} Tc
	;
```
- **Purpose**: Determine the "low" source temperature based on a given source temperature `T_source[u,p,t]`.
- **Logic**:
  1. **Check Condition**: `if min{Tc in HP_Tsource} Tc >= T_source[u,p,t]`
     - If the minimum value in `HP_Tsource` (which is -20°C) is greater than or equal to `T_source[u,p,t]`:
       - Use the minimum value in `HP_Tsource`.
     - Otherwise:
       - Find the maximum value in `HP_Tsource` that is less than `T_source[u,p,t]`.
  2. **Example**:
     - If `T_source[u,p,t] = -25°C`, then `min{Tc in HP_Tsource} Tc = -20°C`, which is greater than `T_source[u,p,t]`, so `HP_Tsource_low` would be -20°C.
     - If `T_source[u,p,t] = 0°C`, the condition fails, so it finds the maximum value in `HP_Tsource` that is less than 0°C, which is -2°C.

### Summary
- **`HP_Tsource_high`**: Determines the appropriate higher bound temperature. It’s either the highest temperature in `HP_Tsource` if its less than or equal to `T_source[u,p,t]`, or the smallest temperature in `HP_Tsource` thats still higher than or equal to `T_source[u,p,t]`.
- **`HP_Tsource_low`**: Determines the appropriate lower bound temperature. It’s either the lowest temperature in `HP_Tsource` if its greater than or equal to `T_source[u,p,t]`, or the largest temperature in `HP_Tsource` thats still lower than `T_source[u,p,t]`.

These parameters help ensure that the heat pump operates within efficient temperature ranges relative to the source temperature `T_source[u,p,t]`.
'''


*/


#-Exergetic efficiency
#---------------------------------------------------------------------#
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

	/*
'''
This code snippet calculates the efficiency of heat pumps (`HP_Eta`) based on source and sink temperatures. It defines parameters to determine the nominal efficiency (`HP_Eta_nominal`) and then uses interpolation to find the effective efficiency based on given supply and source temperatures. Here’s a detailed breakdown:

### Default Nominal Efficiency
```text
param HP_Eta_nominal{u in UnitsOfType[HeatPump], Th in HP_Tsink, Tc in HP_Tsource} default 0.3;  # -
```
- This parameter sets a default nominal efficiency for heat pumps, initially set to 0.3 (or 30%) for each combination of sink and source temperatures.
Actual values will be parsed from the HP_parameters.text

### Low Efficiency Parameter
```text
param HP_Eta_low{h in House, u in UnitsOfType[HeatPump] inter UnitsOfHouse[h], p in Period, t in Time[p], T in HP_Tsupply} :=
	if HP_Tsource_high[u, p, t] == HP_Tsource_low[u, p, t] then
		HP_Eta_nominal[u, HP_Tsink_low[h, p, t, T], HP_Tsource_low[u, p, t]]
	else
		HP_Eta_nominal[u, HP_Tsink_low[h, p, t, T], HP_Tsource_low[u, p, t]] +
		(T_source[u, p, t] - HP_Tsource_low[u, p, t]) * (HP_Eta_nominal[u, HP_Tsink_low[h, p, t, T], HP_Tsource_high[u, p, t]] - HP_Eta_nominal[u, HP_Tsink_low[h, p, t, T], HP_Tsource_low[u, p, t]]) / (HP_Tsource_high[u, p, t] - HP_Tsource_low[u, p, t]);
	;

	that is HP_Eta_nominal_low + (T_source - lower_bound_HP_temp)*(higher_bound_ETA_nominal - lower_bound_ETA_nomial)/(HP_Tsource_high - HP_Tsource_low)
```
- **Purpose**: Calculate the "low" efficiency of the heat pump.
- **Logic**:
  1. **Condition**: `if HP_Tsource_high[u, p, t] == HP_Tsource_low[u, p, t]`
     - If the high and low source temperatures are the same, use the nominal efficiency for the low sink and source temperature.
  2. **Interpolation**:
     - Otherwise, use linear interpolation to calculate efficiency based on the source temperature.
     - `HP_Eta_nominal[u, HP_Tsink_low[h, p, t, T], HP_Tsource_low[u, p, t]]` is the nominal efficiency for the low sink and source temperatures.
     - The interpolation adjusts the nominal efficiency based on the difference between the actual source temperature and the low source temperature, scaled by the efficiency difference between the high and low source temperatures.

### High Efficiency Parameter
```text
param HP_Eta_high{h in House, u in UnitsOfType[HeatPump] inter UnitsOfHouse[h], p in Period, t in Time[p], T in HP_Tsupply} :=
	if HP_Tsource_high[u, p, t] == HP_Tsource_low[u, p, t] then
		HP_Eta_nominal[u, HP_Tsink_high[h, p, t, T], HP_Tsource_low[u, p, t]]
	else
		HP_Eta_nominal[u, HP_Tsink_high[h, p, t, T], HP_Tsource_low[u, p, t]] +
		(T_source[u, p, t] - HP_Tsource_low[u, p, t]) * (HP_Eta_nominal[u, HP_Tsink_high[h, p, t, T], HP_Tsource_high[u, p, t]] - HP_Eta_nominal[u, HP_Tsink_high[h, p, t, T], HP_Tsource_low[u, p, t]]) / (HP_Tsource_high[u, p, t] - HP_Tsource_low[u, p, t]);
	;
```
- **Purpose**: Calculate the "high" efficiency of the heat pump.
- **Logic**:
  1. **Condition**: `if HP_Tsource_high[u, p, t] == HP_Tsource_low[u, p, t]`
     - If the high and low source temperatures are the same, use the nominal efficiency for the high sink and low source temperature.
  2. **Interpolation**:
     - Otherwise, use linear interpolation to calculate efficiency based on the source temperature.
     - `HP_Eta_nominal[u, HP_Tsink_high[h, p, t, T], HP_Tsource_low[u, p, t]]` is the nominal efficiency for the high sink and low source temperatures.
     - The interpolation adjusts the nominal efficiency based on the difference between the actual source temperature and the low source temperature, scaled by the efficiency difference between the high and low source temperatures.

### Overall Efficiency Parameter
```text
param HP_Eta{h in House, u in UnitsOfType[HeatPump] inter UnitsOfHouse[h], p in Period, t in Time[p], T in HP_Tsupply} :=
	if HP_Tsink_high[h, p, t, T] == HP_Tsink_low[h, p, t, T] then
		HP_Eta_low[h, u, p, t, T]
	else
		HP_Eta_low[h, u, p, t, T] +
		(T - HP_Tsink_low[h, p, t, T]) * (HP_Eta_high[h, u, p, t, T] - HP_Eta_low[h, u, p, t, T]) / (HP_Tsink_high[h, p, t, T] - HP_Tsink_low[h, p, t, T])
	;
```
- **Purpose**: Calculate the overall efficiency of the heat pump.
- **Logic**:
  1. **Condition**: `if HP_Tsink_high[h, p, t, T] == HP_Tsink_low[h, p, t, T]`
     - If the high and low sink temperatures are the same, use the low efficiency.
  2. **Interpolation**:
     - Otherwise, use linear interpolation to calculate efficiency based on the supply temperature.
     - `HP_Eta_low[h, u, p, t, T]` is the efficiency for the low sink and source temperatures.
     - The interpolation adjusts the low efficiency based on the difference between the actual supply temperature and the low sink temperature, scaled by the efficiency difference between the high and low sink temperatures.

### Summary
- **Nominal Efficiency**: `HP_Eta_nominal` defines a default efficiency for each combination of sink and source temperatures.
- **Low Efficiency (`HP_Eta_low`)**: Interpolates or selects the nominal efficiency based on the low sink temperature and the source temperature.
- **High Efficiency (`HP_Eta_high`)**: Interpolates or selects the nominal efficiency based on the high sink temperature and the source temperature.
- **Overall Efficiency (`HP_Eta`)**: Interpolates between the low and high efficiencies based on the supply temperature to find the overall efficiency.

These parameters ensure the heat pumps efficiency is accurately represented based on varying sink and source temperatures.


'''
	
	*/
	
#-Power	consumption ratio
#---------------------------------------------------------------------#
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
#---------------------------------------------------------------------#
param HP_COP{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source[u,p,t] and HP_Eta[h,u,p,t,T]*(T+273.15)/(T_source[u,p,t]-T) < max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta[h,u,p,t,T]*(T+273.15)/(T-T_source[u,p,t])
	else
		max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )
	;	
	#-

#-GENERAL DATA
#-Part-load
#---------------------------------------------------------------------#
param HP_partload_max{u in UnitsOfType['HeatPump']} default 1.0;		#-
  
# ----------------------------------------- VARIABLES ---------------------------------------
var HP_E_heating{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} >= 0,<= Units_Fmax[u]*HP_COP[h,u,p,t,T];	#kW

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-Heating
subject to HP_EB_c1{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in HP_Tsupply: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = HP_COP[h,u,p,t,T]*HP_E_heating[h,u,p,t,T]; 									#kW

subject to HP_EB_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0; 														#kW

#--Totals
#-Attention! This is an averaged power consumption value over the whole operation set
subject to HP_c1{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply}(HP_E_heating[h,u,p,t,T]);												#kW

#--Sizing 
subject to HP_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{T in HP_Tsupply} (HP_E_heating[h,u,p,t,T]/HP_Pmax[h,u,p,t,T]) <= Units_Mult[u]*HP_partload_max[u];							#kW

#-Need of technical buffer tank (defrost & hydraulic decoupling) if no floor heating & cycle inversion
subject to HP_c4{h in House,ui in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
Units_Mult[uj] >= if Th_supply_0[h] > 50 then 0.015*Units_Mult[ui]*HP_Eta_nominal[ui,35,20]*(35+273.15)/(35 - (20)) else 0;			#m3

param DHN_CO2_efficiency default 0.95; # The Innovative Concept of Cold District Heating Networks: A Literature Review, Marco Pellegrini
subject to DHN_heat{h in House, u in {'HeatPump_DHN_'&h}, p in Period, t in Time[p]}:
Units_demand['Heat',u,p,t]*DHN_CO2_efficiency = sum{st in StreamsOfUnit[u], se in ServicesOfStream[st]} Streams_Q[se,st,p,t] - sum{st in StreamsOfUnit[u], T in HP_Tsupply: T = Streams_Tin[st,p,t]} HP_E_heating[h,u,p,t,T]; 									#kW

subject to enforce_DHN{h in House, u in {'DHN_hex_in_'&h}, v in {'HeatPump_DHN_'&h}}:
0.95 * sum{p in PeriodStandard, t in Time[p]}(House_Q_heating[h,p,t]* dp[p] * dt[p]) <= sum{p in PeriodStandard, t in Time[p]} (Units_demand['Heat',u,p,t]  * dp[p] * dt[p] + sum{st in StreamsOfUnit[v], se in ServicesOfStream[st]} (Streams_Q[se,st,p,t] * dp[p] * dt[p]));

#--Only one type of heat pump per house
subject to max_one_HeatPump_per_house{h in House}:
sum{u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]} Units_Use[u] <= 1;
#-----------------------------------------------------------------------------------------------------------------------

