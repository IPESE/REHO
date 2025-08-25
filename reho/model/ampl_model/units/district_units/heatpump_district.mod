#####################################################################################################
# Heat Pump Model (District) - AMPL
# 
# All the data and model above are derived from heatpump.mod (building-scale)
# Differences are :
# - heat produced is available as supply to Heat layer (while heat pump at building-scale provides heat HeatCascade)
# - there is only one heat pump per district, hence Set House is not considered here
#
#####################################################################################################

#param HP_district_mult{h in House} default 0;

# Temperature of the heat source for each unit, period, and time step.
param T_source{u in UnitsOfType['HeatPump'], p in Period, t in Time[p]} default 8;
set HP_Tsupply default {80};

# Set of available sink temperatures (common target temperatures for heating)
set HP_Tsink default {60};

# Interpolation of the closest available sink temperature (upper and lower bounds)
param HP_Tsink_high{p in Period, t in Time[p], T in HP_Tsupply} :=
    if max{Th in HP_Tsink} Th <= T then max{Th in HP_Tsink} Th
    else min{Th in HP_Tsink: Th >= T} Th;

param HP_Tsink_low{p in Period, t in Time[p], T in HP_Tsupply} :=
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

param HP_Eta_low{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

param HP_Eta_high{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]]
	else	
		HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_high[u,p,t]]-HP_Eta_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

# Interpolates the efficiency of the heat pump based on the source and sink temperatures
param HP_Eta{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
  if HP_Tsink_high[p,t,T] == HP_Tsink_low[p,t,T] then
      HP_Eta_low[u,p,t,T]  # Use the lower bound efficiency if no interpolation is needed
  else
      # Linear interpolation based on supply temperature T
      HP_Eta_low[u,p,t,T] +
      (T - HP_Tsink_low[p,t,T]) * (HP_Eta_high[u,p,t,T] - HP_Eta_low[u,p,t,T]) / (HP_Tsink_high[p,t,T] - HP_Tsink_low[p,t,T]);

 # Power consumption ratio (values get updated from HP_parameters.txt file)
param HP_Pmax_nominal{u in UnitsOfType['HeatPump'],Th in HP_Tsink,Tc in HP_Tsource} default 1.00;

param HP_Pmax_low{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_low[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);
	
param HP_Pmax_high{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsource_high[u,p,t] == HP_Tsource_low[u,p,t] then
		HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]]
	else
		HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]] +
		(T_source[u,p,t]-HP_Tsource_low[u,p,t])*(HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_high[u,p,t]]-HP_Pmax_nominal[u,HP_Tsink_high[p,t,T],HP_Tsource_low[u,p,t]])/(HP_Tsource_high[u,p,t]-HP_Tsource_low[u,p,t]);

# Maximum power consumption (Pmax) interpolation
param HP_Pmax{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if HP_Tsink_high[p,t,T] == HP_Tsink_low[p,t,T] then
		HP_Pmax_low[u,p,t,T] + 0.01
	else		
		HP_Pmax_low[u,p,t,T] + 0.01 +
		(T - HP_Tsink_low[p,t,T])*(HP_Pmax_high[u,p,t,T]-HP_Pmax_low[u,p,t,T])/(HP_Tsink_high[p,t,T]-HP_Tsink_low[p,t,T]);

# Coefficient of performance (COP) calculation
param HP_COP{u in UnitsOfType['HeatPump'],p in Period,t in Time[p],T in HP_Tsupply} :=
	if T > T_source[u,p,t] and HP_Eta[u,p,t,T]*(T+273.15)/(T_source[u,p,t]-T) < max{Th in HP_Tsink,Tc in HP_Tsource}( HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc) )	then
		HP_Eta[u,p,t,T]*(T+273.15)/(T-T_source[u,p,t])
	else
		max{Th in HP_Tsink,Tc in HP_Tsource}(HP_Eta_nominal[u,Th,Tc]*(T+273.15)/(T-Tc));

# Declaring heating power variable
var HP_Power{u in UnitsOfType['HeatPump'], p in Period, t in Time[p], T in HP_Tsupply} >= 0, <= Units_Fmax[u]*HP_COP[u,p,t,T];

# Power input
subject to HP_power_input{u in UnitsOfType['HeatPump'], p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] = sum{T in HP_Tsupply} HP_Power[u,p,t,T];

# Sizing
subject to HP_sizing{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
	sum{T in HP_Tsupply} HP_COP[u,p,t,T] * (HP_Power[u,p,t,T]/HP_Pmax[u,p,t,T]) <= Units_Mult[u];

# Heating output
subject to HP_heating_output{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
	Units_supply['Heat',u,p,t] = sum{T in HP_Tsupply} HP_COP[u,p,t,T]*HP_Power[u,p,t,T];

# constraint to enforce the installation of HP_district with specific multiplier
subject to enforce_HP_district_mult{u in UnitsOfType['HeatPump'],p in Period,t in Time[p]}:
Units_Mult[u] = 400; #HP_district_mult[u];