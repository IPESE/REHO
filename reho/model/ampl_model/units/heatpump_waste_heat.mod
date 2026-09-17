#####################################################################################################
# Heat Pump Model - AMPL
# 
# This model represents the operation of a heat pump with different heat sources (air, water, geothermal).
# It calculates:
# 1. The efficiency of the heat pump based on source and sink temperatures.
# 2. The power consumption and heating energy delivered.
# 3. Constraints ensuring proper operation and sizing.
#
# Key Parameters:
# - HP_Tsink: Available sink temperatures.
# - HP_Tsource: Available source temperatures.
# - HP_Eta: Efficiency of the heat pump.
# - HP_COP: Coefficient of performance (heat output / power input).
# - HP_Pmax: Maximum power consumption.
#
# Constraints:
# - Ensures only one type of heat pump per house.
# - Enforces energy balance for heating.
# - Limits power consumption based on efficiency.
#####################################################################################################

# Temperature of the heat source for each unit, period, and time step.
param T_source_WH{u in UnitsOfType['HeatPump_WH'], p in Period, t in Time[p]} := 20;

# Set of available sink temperatures (common target temperatures for heating)
set HP_Tsink_WH default {35,45,55};  # Degrees Celsius

# Interpolation of the closest available sink temperature (upper and lower bounds)
param HP_Tsink_WH_high{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=
    if max{Th in HP_Tsink_WH} Th <= T then max{Th in HP_Tsink_WH} Th
    else min{Th in HP_Tsink_WH: Th >= T} Th;

param HP_Tsink_WH_low{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=
    if min{Th in HP_Tsink_WH} Th >= T then min{Th in HP_Tsink_WH} Th
    else max{Th in HP_Tsink_WH: Th < T} Th;

# Set of available source temperatures
set HP_Tsource_WH default {-20,-15,-10,-7,-2,2,7,10,15,20};  # Degrees Celsius

# Interpolation of the closest available source temperature (upper and lower bounds)
param HP_Tsource_WH_high{u in UnitsOfType['HeatPump_WH'], p in Period, t in Time[p]} :=
    if max{Tc in HP_Tsource_WH} Tc <= T_source_WH[u,p,t] then max{Tc in HP_Tsource_WH} Tc
    else min{Tc in HP_Tsource_WH: Tc >= T_source_WH[u,p,t]} Tc;

param HP_Tsource_WH_low{u in UnitsOfType['HeatPump_WH'], p in Period, t in Time[p]} :=
    if min{Tc in HP_Tsource_WH} Tc >= T_source_WH[u,p,t] then min{Tc in HP_Tsource_WH} Tc
    else max{Tc in HP_Tsource_WH: Tc < T_source_WH[u,p,t]} Tc;

# Default nominal efficiency for heat pumps (values get updated from HP_parameters.txt file)
param HP_Eta_nominal_WH{u in UnitsOfType['HeatPump_WH'], Th in HP_Tsink_WH, Tc in HP_Tsource_WH} default 0.3;

param HP_Eta_low_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_WH_high[u,p,t] == HP_Tsource_WH_low[u,p,t] then
		HP_Eta_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]]
	else
		HP_Eta_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]] +
		(T_source_WH[u,p,t]-HP_Tsource_WH_low[u,p,t])*(HP_Eta_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_high[u,p,t]]-HP_Eta_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]])/(HP_Tsource_WH_high[u,p,t]-HP_Tsource_WH_low[u,p,t]);

param HP_Eta_high_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_WH_high[u,p,t] == HP_Tsource_WH_low[u,p,t] then
		HP_Eta_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]]
	else	
		HP_Eta_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]] +
		(T_source_WH[u,p,t]-HP_Tsource_WH_low[u,p,t])*(HP_Eta_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_high[u,p,t]]-HP_Eta_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]])/(HP_Tsource_WH_high[u,p,t]-HP_Tsource_WH_low[u,p,t]);

# Interpolates the efficiency of the heat pump based on the source and sink temperatures
param HP_Eta_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
  if HP_Tsink_WH_high[h,p,t,T] == HP_Tsink_WH_low[h,p,t,T] then
      HP_Eta_low_WH[h,u,p,t,T]  # Use the lower bound efficiency if no interpolation is needed
  else
      # Linear interpolation based on supply temperature T
      HP_Eta_low_WH[h,u,p,t,T] +
      (T - HP_Tsink_WH_low[h,p,t,T]) * (HP_Eta_high_WH[h,u,p,t,T] - HP_Eta_low_WH[h,u,p,t,T]) / (HP_Tsink_WH_high[h,p,t,T] - HP_Tsink_WH_low[h,p,t,T]);

 # Power consumption ratio (values get updated from HP_parameters.txt file)
param HP_Pmax_nominal_WH{u in UnitsOfType['HeatPump_WH'],Th in HP_Tsink_WH,Tc in HP_Tsource_WH} default 1.00;

param HP_Pmax_low_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_WH_high[u,p,t] == HP_Tsource_WH_low[u,p,t] then
		HP_Pmax_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]]
	else
		HP_Pmax_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]] +
		(T_source_WH[u,p,t]-HP_Tsource_WH_low[u,p,t])*(HP_Pmax_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_high[u,p,t]]-HP_Pmax_nominal_WH[u,HP_Tsink_WH_low[h,p,t,T],HP_Tsource_WH_low[u,p,t]])/(HP_Tsource_WH_high[u,p,t]-HP_Tsource_WH_low[u,p,t]);
	
param HP_Pmax_high_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_WH_high[u,p,t] == HP_Tsource_WH_low[u,p,t] then
		HP_Pmax_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]]
	else
		HP_Pmax_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]] +
		(T_source_WH[u,p,t]-HP_Tsource_WH_low[u,p,t])*(HP_Pmax_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_high[u,p,t]]-HP_Pmax_nominal_WH[u,HP_Tsink_WH_high[h,p,t,T],HP_Tsource_WH_low[u,p,t]])/(HP_Tsource_WH_high[u,p,t]-HP_Tsource_WH_low[u,p,t]);

# Maximum power consumption (Pmax) interpolation
param HP_Pmax_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_WH_high[h,p,t,T] == HP_Tsink_WH_low[h,p,t,T] then
		HP_Pmax_low_WH[h,u,p,t,T] + 0.01
	else		
		HP_Pmax_low_WH[h,u,p,t,T] + 0.01 +
		(T - HP_Tsink_WH_low[h,p,t,T])*(HP_Pmax_high_WH[h,u,p,t,T]-HP_Pmax_low_WH[h,u,p,t,T])/(HP_Tsink_WH_high[h,p,t,T]-HP_Tsink_WH_low[h,p,t,T]);

# Coefficient of performance (COP) calculation
param HP_COP_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source_WH[u,p,t] and HP_Eta_WH[h,u,p,t,T]*(T+273.15)/(T_source_WH[u,p,t]-T) < max{Th in HP_Tsink_WH,Tc in HP_Tsource_WH}( HP_Eta_nominal_WH[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta_WH[h,u,p,t,T]*(T+273.15)/(T-T_source_WH[u,p,t])
	else
		max{Th in HP_Tsink_WH,Tc in HP_Tsource_WH}(HP_Eta_nominal_WH[u,Th,Tc]*(T+273.15)/(T-Tc));

# Declaring heating power variable
var HP_Power_WH{h in House, u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in HP_Tsupply} >= 0, <= Units_Fmax[u]*HP_COP_WH[h,u,p,t,T];

# Heating output
subject to HP_heating_output_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in HP_Tsupply: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = HP_COP_WH[h,u,p,t,T]*HP_Power_WH[h,u,p,t,T];

# Power input
subject to HP_power_input_WH{h in House, u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply} HP_Power_WH[h,u,p,t,T];

# Sizing
subject to HP_sizing_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
	sum{T in HP_Tsupply} HP_COP_WH[h,u,p,t,T]*(HP_Power_WH[h,u,p,t,T]/HP_Pmax_WH[h,u,p,t,T]) <= Units_Mult[u];

# DWH production
subject to HP_EB_c2_WH{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0;

# Need of technical buffer tank (defrost & hydraulic decoupling) if no floor heating & cycle inversion
subject to HP_c4_WH{h in House,ui in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
	Units_Mult[uj] >= if Th_supply_0[h] > 50 then 1000*0.005*Units_Mult[ui]*HP_Eta_nominal_WH[ui,35,20]*(35+273.15)/(35 - (20)) else 0;			#L

# District Heating Network Efficiency Parameter
param DHN_CO2_efficiency_WH default 0.95;  # Efficiency based on literature

# District heating network constraints
#subject to DHN_heat_WH{h in House, u in {'HeatPump_WH_DHN_'&h}, p in Period, t in Time[p]}:
#	Units_demand['Heat',u,p,t]*DHN_CO2_efficiency_WH = sum{st in StreamsOfUnit[u], se in ServicesOfStream[st]} Streams_Q[se,st,p,t] - sum{st in StreamsOfUnit[u], T in HP_Tsupply: T = Streams_Tin[st,p,t]} HP_Power_WH[h,u,p,t,T];

#subject to enforce_DHN_WH{h in House, u in {'DHN_hex_'&h}, v in {'HeatPump_WH_DHN_'&h}}:
#	0.95 * sum{p in PeriodStandard, t in Time[p]}(House_Q_heating[h,p,t]* dp[p] * dt[p]) <= sum{p in PeriodStandard, t in Time[p]} (Units_demand['Heat',u,p,t]  * dp[p] * dt[p] + sum{st in StreamsOfUnit[v], se in ServicesOfStream[st]} (Streams_Q[se,st,p,t] * dp[p] * dt[p]));

param COP_20_80_DHN
subject to HP_SourceHeat_Limit {h in House, u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h], p in Period, t in Time[p]
}:
  sum{T in HP_Tsupply}
    (HP_COP_WH[h,u,p,t,T] - 1) * HP_Power_WH[h,u,p,t,T] +
  <= waste_heat_available[p,t];

subject to HeatPump_WH_only_if_one_HP{h in House,u in UnitsOfType['HeatPump_WH'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
	Units_Use[u] <= sum{uu in UnitsOfType['HeatPump']} Units_Use[uu];