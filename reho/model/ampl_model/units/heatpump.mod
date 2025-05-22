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
param T_source{u in UnitsOfType['HeatPump'], p in Period, t in Time[p]};

# Set of available sink temperatures (common target temperatures for heating)
set HP_Tsink default {35,45,55};  # Degrees Celsius

# Interpolation of the closest available sink temperature (upper and lower bounds)
param HP_Tsink_high{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=
    if max{Th in HP_Tsink} Th <= T then max{Th in HP_Tsink} Th
    else min{Th in HP_Tsink: Th >= T} Th;

param HP_Tsink_low{h in House, p in Period, t in Time[p], T in HP_Tsupply} :=
    if min{Th in HP_Tsink} Th >= T then min{Th in HP_Tsink} Th
    else max{Th in HP_Tsink: Th < T} Th;

# Set of available source temperatures
set HP_Tsource default {-20,-15,-10,-7,-2,2,7,10,15,20};  # Degrees Celsius

# Interpolation of the closest available source temperature (upper and lower bounds)
param HP_Tsource_high{u in UnitsOfType['HeatPump'], p in Period, t in Time[p]} :=
    if max{Tc in HP_Tsource} Tc <= T_source[u,p,t] then max{Tc in HP_Tsource} Tc
    else min{Tc in HP_Tsource: Tc >= T_source[u,p,t]} Tc;

param HP_Tsource_low{u in UnitsOfType['HeatPump'], p in Period, t in Time[p]} :=
    if min{Tc in HP_Tsource} Tc >= T_source[u,p,t] then min{Tc in HP_Tsource} Tc
    else max{Tc in HP_Tsource: Tc < T_source[u,p,t]} Tc;

# Default nominal efficiency for heat pumps (values get updated from HP_parameters.txt file)
param HP_Eta_nominal{u in UnitsOfType['HeatPump'], Th in HP_Tsink, Tc in HP_Tsource} default 0.3;

param HP_Eta_low{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

param HP_Eta_high{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]]
	else	
		HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

# Interpolates the efficiency of the heat pump based on the source and sink temperatures
param HP_Eta{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
  if HP_Tsink_high[h,p,t,T] == HP_Tsink_low[h,p,t,T] then
      HP_Eta_low[h,u,p,t,T]  # Use the lower bound efficiency if no interpolation is needed
  else
      # Linear interpolation based on supply temperature T
      HP_Eta_low[h,u,p,t,T] +
      (T - HP_Tsink_low[h,p,t,T]) * (HP_Eta_high[h,u,p,t,T] - HP_Eta_low[h,u,p,t,T]) / (HP_Tsink_high[h,p,t,T] - HP_Tsink_low[h,p,t,T]);

 # Power consumption ratio (values get updated from HP_parameters.txt file)
param HP_Pmax_nominal{u in UnitsOfType['HeatPump'],Th in HP_Tsink,Tc in HP_Tsource} default 1.00;

param HP_Pmax_low{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_low[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	
param HP_Pmax_high{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_high[h,p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

# Maximum power consumption (Pmax) interpolation
param HP_Pmax{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[h,p,t,T] == HP_Tsink_low[h,p,t,T] then
		HP_Pmax_low[h,u,p,t,T] + 0.01
	else		
		HP_Pmax_low[h,u,p,t,T] + 0.01 +
		(T - HP_Tsink_low[h,p,t,T])*(HP_Pmax_high[h,u,p,t,T]-HP_Pmax_low[h,u,p,t,T])/(HP_Tsink_high[h,p,t,T]-HP_Tsink_low[h,p,t,T]);

# Coefficient of performance (COP) calculation
param HP_COP{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source[u,p,t] and HP_Eta[h,u,p,t,T]*(T+273.15)/(T_source[u,p,t]-T) < max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta[h,u,p,t,T]*(T+273.15)/(T-T_source[u,p,t])
	else
		max{Th in HP_Tsink,Tc in HP_Tsource}(HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc));

# Declaring heating power variable
var HP_Power{h in House, u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h], p in Period, t in Time[p], T in HP_Tsupply} >= 0, <= Units_Fmax[u]*HP_COP[h,u,p,t,T];

# Heating output
subject to HP_heating_output{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p],T in HP_Tsupply: T = Streams_Tin[st,p,t]}:
sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = HP_COP[h,u,p,t,T]*HP_Power[h,u,p,t,T];

# Power input
subject to HP_power_input{h in House, u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply} HP_Power[h,u,p,t,T];

# Sizing
subject to HP_sizing{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
	sum{T in HP_Tsupply} HP_COP[h,u,p,t,T]*(HP_Power[h,u,p,t,T]/HP_Pmax[h,u,p,t,T]) <= Units_Mult[u];

# DWH production
subject to HP_EB_c2{h in House,u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u]: Streams_Tin[st,p,t] < 55} Streams_Q['DHW',st,p,t] = 0;

# Need of technical buffer tank (defrost & hydraulic decoupling) if no floor heating & cycle inversion
subject to HP_c4{h in House,ui in UnitsOfType['HeatPump'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
	Units_Mult[uj] >= if Th_supply_0[h] > 50 then 1000*0.005*Units_Mult[ui]*HP_Eta_nominal[ui,35,20]*(35+273.15)/(35 - (20)) else 0;			#L

# Ensures only one type of heat pump per house
subject to max_one_HeatPump_per_house{h in House}:
    sum{u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]} Units_Use[u] <= 1;

# District Heating Network Efficiency Parameter
param DHN_CO2_efficiency default 0.95;  # Efficiency based on literature

# District heating network constraints
subject to DHN_heat{h in House, u in {'HeatPump_DHN_'&h}, p in Period, t in Time[p]}:
	Units_demand['Heat',u,p,t]*DHN_CO2_efficiency = sum{st in StreamsOfUnit[u], se in ServicesOfStream[st]} Streams_Q[se,st,p,t] - sum{st in StreamsOfUnit[u], T in HP_Tsupply: T = Streams_Tin[st,p,t]} HP_Power[h,u,p,t,T];

subject to enforce_DHN{h in House, u in {'DHN_hex_'&h}, v in {'HeatPump_DHN_'&h}}:
	0.95 * sum{p in PeriodStandard, t in Time[p]}(House_Q_heating[h,p,t]* dp[p] * dt[p]) <= sum{p in PeriodStandard, t in Time[p]} (Units_demand['Heat',u,p,t]  * dp[p] * dt[p] + sum{st in StreamsOfUnit[v], se in ServicesOfStream[st]} (Streams_Q[se,st,p,t] * dp[p] * dt[p]));

param HeatPump_Air_install{h in House} default 0;
param HeatPump_Geothermal_install{h in House} default 0;

#subject to enforce_HeatPump{h in House}:
	#sum{u in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]: u not in {'HeatPump_DHN_'&h}} Units_Use[u] = HeatPump_install[h];

subject to enforce_HeatPump_Air{h in House,u in {'HeatPump_Air_'&h}}:
	Units_Use[u] = HeatPump_Air_install[h];

subject to enforce_HeatPump_Geothermal{h in House,u in {'HeatPump_Geothermal_'&h}}:
	Units_Use[u] = HeatPump_Geothermal_install[h];