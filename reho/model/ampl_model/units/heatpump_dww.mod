######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Waste water heat pump
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-Heat pump recovering heat from the domestic waste water (DWW) leaving the building end-uses,
# and supplying the domestic hot water (DHW) service.
#-The waste water leaves the end-use at DWW_T_drain and is cooled to DWW_T_reject before being
# rejected to the sewer. The recoverable thermal power follows directly from the drain flow rate.
#-References :
# [1]	Bertrand, Waste heat valorisation at multiple scales, PhD Thesis, 2017.

#-Waste water temperatures
param DWW_T_drain  >= 0, default 35;					#deg C		leaving the end-use [1, Sec. 3.2.2.1]
param DWW_T_reject >= 0, <= DWW_T_drain, default 20;	#deg C		rejected to the sewer

#-Input data
param DWW_flowrate{h in House, p in Period, t in Time[p]} >= 0 default 0;	#L/h

#-Recoverable thermal power in the waste water stream
param Q_DWW{h in House, p in Period, t in Time[p]} :=
	DWW_flowrate[h,p,t] * rho_water * cp_water_kj * (DWW_T_drain - DWW_T_reject) / 3600;	#kW rho_water and cp_water_kj are both already declared in sub_problem.mod:60-61

#-Available sink and source temperatures (values get updated from DWW_parameters.txt)
set DWW_Tsink   default {35,45,55};						#deg C
set DWW_Tsource default {10,15,20,25,30,35};			#deg C

#-Nominal performance (values get updated from DWW_parameters.txt)
param DWW_Eta_nominal{u in UnitsOfType['HeatPump_DWW'], Th in DWW_Tsink, Tc in DWW_Tsource}  default 0.46;
param DWW_Pmax_nominal{u in UnitsOfType['HeatPump_DWW'], Th in DWW_Tsink, Tc in DWW_Tsource} default 1.00;

#-Evaporator temperature: the waste water glides from DWW_T_drain to DWW_T_reject, so the
# evaporator sees their mean (log-mean and arithmetic mean agree to <0.1 K over this range)
param DWW_T_source := (DWW_T_drain + DWW_T_reject)/2;	#deg C

# Interpolation of the closest available sink temperature (upper and lower bounds)
param DWW_Tsource_high :=
	if max{Tc in DWW_Tsource} Tc <= DWW_T_source then max{Tc in DWW_Tsource} Tc
	else min{Tc in DWW_Tsource: Tc >= DWW_T_source} Tc;

param DWW_Tsource_low :=
	if min{Tc in DWW_Tsource} Tc >= DWW_T_source then min{Tc in DWW_Tsource} Tc
	else max{Tc in DWW_Tsource: Tc <  DWW_T_source} Tc;

#-Second-law efficiency, interpolated on the source temperature. The sink is read directly
# from the grid: every T used is a member of DWW_Tsink, so bracketing it would be a no-op.
param DWW_Eta{u in UnitsOfType['HeatPump_DWW'], Th in DWW_Tsink} :=
	if DWW_Tsource_high = DWW_Tsource_low then
		DWW_Eta_nominal[u,Th,DWW_Tsource_low]
	else
		DWW_Eta_nominal[u,Th,DWW_Tsource_low] + (DWW_T_source - DWW_Tsource_low) *
		(DWW_Eta_nominal[u,Th,DWW_Tsource_high] - DWW_Eta_nominal[u,Th,DWW_Tsource_low]) /
		(DWW_Tsource_high - DWW_Tsource_low);

#-Capacity ratio, same interpolation. The +0.01 mirrors heatpump.mod and keeps the
# Power/DWW_Pmax division in the sizing constraint away from zero.
param DWW_Pmax{u in UnitsOfType['HeatPump_DWW'], Th in DWW_Tsink} :=
	0.01 +
	if DWW_Tsource_high = DWW_Tsource_low then
		DWW_Pmax_nominal[u,Th,DWW_Tsource_low]
	else
		DWW_Pmax_nominal[u,Th,DWW_Tsource_low] + (DWW_T_source - DWW_Tsource_low) *
		(DWW_Pmax_nominal[u,Th,DWW_Tsource_high] - DWW_Pmax_nominal[u,Th,DWW_Tsource_low]) /
		(DWW_Tsource_high - DWW_Tsource_low);

#-Coefficient of performance: Carnot limit times the second-law efficiency.
# The correlation diverges as the lift goes to zero, so it is capped; a sink at or below the
# source temperature is physically meaningless and is disabled by returning 0.
param DWW_COP_max default 10;

param DWW_COP{u in UnitsOfType['HeatPump_DWW'], Th in DWW_Tsink} :=
	if Th > DWW_T_source then
		min(DWW_COP_max, DWW_Eta[u,Th] * (Th + 273.15) / (Th - DWW_T_source))
	else
		0;

#-Electrical power drawn by the compressor, per sink temperature level
var DWW_Power{h in House, u in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h],
              p in Period, t in Time[p], Th in DWW_Tsink} >= 0, <= Units_Fmax[u];	#kW electrical

#-Heating output: the delivered heat enters the heat cascade on the unit's hot stream
subject to DWW_heating_output{h in House, u in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h],
		st in StreamsOfUnit[u], p in Period, t in Time[p], Th in DWW_Tsink:
		Th = Streams_Tin[st,p,t]}:
	sum{se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = DWW_COP[u,Th] * DWW_Power[h,u,p,t,Th];

#-Power input: the compressor draws from the Electricity layer
subject to DWW_power_input{h in House, u in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h],
		p in Period, t in Time[p]}:
	Units_demand['Electricity',u,p,t] = sum{Th in DWW_Tsink} DWW_Power[h,u,p,t,Th];

#-Source availability: the evaporator cannot draw more than the waste water carries
subject to DWW_availability{h in House, u in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h],
		p in Period, t in Time[p]}:
	sum{Th in DWW_Tsink} (DWW_COP[u,Th] - 1) * DWW_Power[h,u,p,t,Th] <= Q_DWW[h,p,t];

#-Sizing: Units_Mult is the installed thermal capacity
subject to DWW_sizing{h in House, u in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h],
		p in Period, t in Time[p]}:
	sum{Th in DWW_Tsink} DWW_COP[u,Th] * (DWW_Power[h,u,p,t,Th] / DWW_Pmax[u,Th]) <= Units_Mult[u];

#-A DHW tank is required: without it there is no DHW demand for this unit to serve
subject to enforce_DHW_tank_if_HeatPump_DWW{h in House}:
	sum{uj in UnitsOfType['WaterTankDHW'] inter UnitsOfHouse[h]} Units_Use[uj] >=
	sum{ui in UnitsOfType['HeatPump_DWW'] inter UnitsOfHouse[h]} Units_Use[ui];