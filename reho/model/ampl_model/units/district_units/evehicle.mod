######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---EV MODEL (EV and CHARGING INFRASTRUCTURE)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-First-order electrical storage model at district level including:
#	1. dis-/charging efficiencies 
#	2. self-discharging efficiency 
#	3. dis-/charging limits
#-References : 
# [1]	F. Oldewurtel et al., Building Control and Storage Management with [...], 2010 
# [2]   M. Koller et al., Defining a Degradation Cost Function for Optimal [...], 2013
# [3]	Z. Dimitrova, Environomic design of vehicle integrated energy systems, 2015
# [4]	Federal Office of Statistic, Comportement de la population en matiere de transports, 2015
# [5]	L. Calearo, A review of data sources for electric vehicle integration studies, 2021
# [6]	https://www.tcs.ch/fr/tests-conseils/conseils/mobilite-electrique/voiture-electrique-2021.php
# [7]	https://www.tcs.ch/fr/tests-conseils/conseils/environnement-mobilite/recharge-electrique.php
# ----------------------------------------- PARAMETERS ---------------------------------------

# Usage
param n_EVperhab{u in UnitsOfType['EV']} default 1; # [4] G 2.1.2.1 on average 0.49 vehicles per dwelling (to be multiplied with persons/dwelling ?)
param n_EVtotperhab default 1.5; # number
param n_EV_max{u in UnitsOfType['EV']} := n_EVperhab[u] * Population;
param n_EVtot_max := n_EVtotperhab * Population;
param ff_EV{u in UnitsOfType['EV']} default 1.56; # person/vehicle [4]
param EV_plugged_out{u in UnitsOfType['EV'], p in Period, t in Time[p]} default 0.15;	# initialized through the function generate_mobility_parameters
param EV_charging_profile{u in UnitsOfType['EV'], p in Period, t in Time[p]} default 0.15;	# initialized through the function generate_mobility_parameters
param tau_relaxation_charging_profile default 0.03; # [-]
param EV_activity{a in Activities,u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}; # [-] initialized through the function generate_mobility_parameters
param max_daily_time_spend_travelling{u in UnitsOfType['EV']} default 0.9; # hours - usually a car spends 1h per day on the move - source : Timo

# Computed parameters to calculate the variation between EV_E_stored (plug_in and plug_out) depending on EV_plugged_out at each interval of time
param storedOut2Out{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} :=  # [-]
	if EV_plugged_out[u,p,prev(t,Time[p])] = 0 then
		1
	else
		min(1,EV_plugged_out[u,p,t]/EV_plugged_out[u,p,prev(t,Time[p])]);
param storedIn2In{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := # [-]
	if EV_plugged_out[u,p,prev(t,Time[p])] = 1 then
		1
	else
		min(1,(1-EV_plugged_out[u,p,t])/(1-EV_plugged_out[u,p,prev(t,Time[p])]));
param storedIn2Out{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := # [-]
	if EV_plugged_out[u,p,prev(t,Time[p])] = 1 then
		0
	else
		max(0,1-(1-EV_plugged_out[u,p,t])/(1-EV_plugged_out[u,p,prev(t,Time[p])]));
param storedOut2In{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := # [-]
	if EV_plugged_out[u,p,prev(t,Time[p])] = 0 then
		0
	else
		max(0,1-EV_plugged_out[u,p,t]/EV_plugged_out[u,p,prev(t,Time[p])]);

# Technical caracteriques
param EV_limit_ch default 0.8;				#-		[2]
param EV_limit_di default 0.2;				#-		[1]
param EV_efficiency default 0.99992;		#-		[1]
param EV_capacity default 70;				#kWh 	[5] and [6]
param EV_eff_travel default 6; 					#km/kWh

# Charging stations
param EV_charger_Power{uc in UnitsOfType['EV_charger']} default 7;			#kW	 	[5] and [7]
param EV_eff_ch default 0.9;				#-		[1] both charging station efficiency and battery efficiency
param EV_eff_di default 0.9;				#-		[1]
param EV_supply_ext{a in Activities, p in Period, t in Time[p]} default 0; #kWh
param Cost_supply_ext{ p in PeriodStandard, t in Time[p]} default 0; #CHF/kWh

# EV batteries charging outside the district
param EV_charger_Power_ext{d in Districts} default 7; # kW - describes the mean charger power of the overall town (sum of districts)
param share_activity{a in Activities, d in Districts} default 0; # [-] to describe the distribution of EVs plugged out in the other disctricts : default 0 means that there is no interaction with other districts = run as standalone
param Cost_demand_ext{d in Districts, p in PeriodStandard, t in Time[p]} default Cost_supply_network["Electricity",p,t]; #CHF/kWh

# ----------------------------------------- VARIABLES ---------------------------------------
var n_vehicles{u in UnitsOfType['EV']} integer >= 0; # number
var EV_E_stored{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0; # kWh
var EV_E_stored_plug_out{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0; # kWh
var EV_E_stored_plug_in{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0; # kWh
var EV_V2V{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0; # kWh
var EV_supply_travel{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0; # kWh

# charging stations
var n_chargers{uc in UnitsOfType['EV_charger']} integer >= 0;
var EV_demand{u in UnitsOfType['EV'],p in Period,t in Time[p]} >=0; # kWh
var coeff_charging_profile{u in UnitsOfType['EV'],p in Period} >= 0; # [-] only used when forcing a charging profile
var EV_supply{u in UnitsOfType['EV'],p in Period,t in Time[p]} >=0; # kWh
var C2V{uc in UnitsOfType['EV_charger'],u in UnitsOfType['EV'],p in Period,t in Time[p]}>= 0 ; # kWh - Charger to Vehicle
var V2C{uc in UnitsOfType['EV_charger'],u in UnitsOfType['EV'],p in Period,t in Time[p]}>= 0 ; # kWh - Vehicle to Charger

# EV batteries charging outside the district
var EV_demand_ext{a in Activities, d in Districts, u in UnitsOfType['EV'], p in Period, t in Time[p]} >= 0; # kWh
var C2A{uc in UnitsOfType['EV_charger'],a in Activities,p in Period,t in Time[p]}>= 0 ; # kWh - Charger to Activity (i.e. the external load EV_supply_ext)

var EV_revenue_ext{p in Period,t in Time[p]};
var EV_cost_ext{p in Period,t in Time[p]};

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#--Energy balance
subject to EV_EB_c1{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency * (storedOut2Out[u,p,t]*EV_E_stored_plug_out[u,p,prev(t,Time[p])] + storedIn2Out[u,p,t]*EV_E_stored_plug_in[u,p,prev(t,Time[p])]);

subject to EV_EB_c2{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency * (storedIn2In[u,p,t]*EV_E_stored_plug_in[u,p,prev(t,Time[p])] + storedOut2In[u,p,t]*EV_E_stored_plug_out[u,p,prev(t,Time[p])]) -
							EV_supply_travel[u,p,t] - EV_V2V[u,p,t] * (1 - EV_eff_ch * EV_eff_di) +
							(EV_demand[u,p,t]  - EV_supply[u,p,t]) * dt[p];



subject to EV_EB_c3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] =  EV_E_stored_plug_in[u,p,t] + EV_E_stored_plug_out[u,p,t];

subject to EV_EB_upper_bound1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] <= EV_capacity * n_vehicles[u];

subject to EV_EB_upper_bound2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] <= EV_capacity * n_vehicles[u];

subject to EV_EB_upper_bound3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] <= EV_capacity * n_vehicles[u];

# subject to EV_V2V_1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
# EV_V2V[u,p,t] >= EV_supply_travel[u,p,t] - EV_demand[u,p,t]; #question : pq ici il y avait pas le d[t] dans EV_displacement[] * Unit_use * dt ?

subject to EV_chargingconstraint{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
sum {uc in UnitsOfType['EV_charger']}(C2V[uc,u,p,t]/EV_charger_Power[uc]) <= n_vehicles[u] * (1 - EV_plugged_out[u,p,t]);

subject to unidirectional_service{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_supply[u,p,t] = 0;

subject to unidirectional_service2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_V2V[u,p,t] = 0;

# mobility and outside-the-district charging
subject to EV_EB_mobility1{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= n_vehicles[u]* EV_activity['travel',u,p,t] * Mode_Speed[u]; 

subject to EV_EB_mobility2{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_supply_travel[u,p,t] = Units_supply['Mobility',u,p,t]/ ff_EV[u] / EV_eff_travel  - sum{d in Districts}(sum{a in Activities}(EV_demand_ext[a,d,u,p,t]));

subject to EV_chargingprofile1{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_demand[u,p,t] <= coeff_charging_profile[u,p] * EV_charging_profile[u,p,t] * (1 + tau_relaxation_charging_profile); 

subject to EV_chargingprofile2{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_demand[u,p,t] >= coeff_charging_profile[u,p] * EV_charging_profile[u,p,t] * (1 - tau_relaxation_charging_profile); 

subject to external_charging_c1{a in Activities,d in Districts, u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}:
EV_demand_ext[a,d,u,p,t] <= EV_activity[a,u,p,t]* share_activity[a,d]  * n_vehicles[u] * EV_charger_Power_ext[d];

subject to external_charging_c2{d in Districts, u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}:
EV_demand_ext["travel",d,u,p,t] <=0; # During the travel activity, EV can provide pkm, but they do not have charging opportunities. 

# costs and revenues of external charging
subject to external_charging_costs1{ p in PeriodStandard, t in Time[p]}:
EV_revenue_ext[p,t] = Cost_supply_ext[p,t] *sum {a in Activities} EV_supply_ext[a,p,t];

subject to external_charging_costs2{ p in PeriodStandard, t in Time[p]}:
EV_cost_ext[p,t] = sum{d in Districts, a in Activities, u in UnitsOfType['EV']} Cost_demand_ext[d,p,t] * EV_demand_ext[a,d,u,p,t];

subject to external_charging_costs3{ p in PeriodStandard, t in Time[p]}:
ExternalEV_Costs_op[p,t] = (EV_cost_ext[p,t] - EV_revenue_ext[p,t])* dp[p] * dt[p];


#--Stock constraints
#subject to EV_stock_upperbound1{u in UnitsOfType['EV']}:
#n_vehicles[u] <= n_EV_max[u];

#subject to EV_stock_upperbound2:
#sum{u in UnitsOfType['EV']} (n_vehicles[u]) <= n_EVtot_max;


#--Max share and time of travel
subject to EV_maxshare{u in UnitsOfType['EV'],p in PeriodStandard, dist in Distances}:
sum {t in Time[p]}(pkm_supply[u,dist,p,t]) <= max_share[u,dist] * Population * DailyDist[dist] ; 

subject to EV_minshare{u in UnitsOfType['EV'],p in PeriodStandard, dist in Distances}:
sum {t in Time[p]}(pkm_supply[u,dist,p,t]) >= min_share[u,dist] * Population * DailyDist[dist] ; 

#subject to EV_timeoftravel{p in Period,u in UnitsOfType['EV']}:
#sum {t in Time[p]}(Units_supply['Mobility',u,p,t])/ff_EV[u] /Mode_Speed[u]  <= max_daily_time_spend_travelling[u] * n_vehicles[u] ; 


#--SoC constraints
subject to EV_c5a{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] <= EV_limit_ch * EV_capacity * n_vehicles[u];											#kWh

subject to EV_c6a{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] >= EV_limit_di * EV_capacity * n_vehicles[u];											#kWh


subject to EV_c5b{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] <= EV_limit_ch*EV_capacity*n_vehicles[u]* (1-EV_plugged_out[u,p,t]);											#kWh

subject to EV_c6b{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] >= EV_limit_di*EV_capacity*n_vehicles[u]* (1-EV_plugged_out[u,p,t]);											#kWh
	
	
subject to EV_c5c{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] <= (EV_limit_ch*EV_capacity * n_vehicles[u] + EV_supply_travel[u,p,t]) * EV_plugged_out[u,p,t];										#kWh

subject to EV_c6c{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] >= (EV_limit_di*EV_capacity * n_vehicles[u] + EV_supply_travel[u,p,t]) * EV_plugged_out[u,p,t];										#kWh
																			#-
	
subject to EV_c7a{u in UnitsOfType['EV']}:
Units_Mult[u] = EV_capacity*n_vehicles[u];  #kWh

#subject to EV_c8{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=4}:
#EV_E_stored[u,p,t] >= EV_limit_ch*EV_capacity*n_vehicles[u];											#kWh


#--Charging stations
subject to chargingstation_c1{uc in UnitsOfType['EV_charger'],p in Period,t in Time[p]}:
Units_demand['Electricity',uc,p,t] + Units_supply['Electricity',uc,p,t] <= EV_charger_Power[uc] * n_chargers[uc];								#kW

subject to chargingstation_c2{uc in UnitsOfType['EV_charger'],p in Period,t in Time[p]}:
Units_demand['Electricity',uc,p,t] * EV_eff_ch  = sum {u in UnitsOfType['EV']}(C2V[uc,u,p,t])+ sum{a in Activities} (C2A[uc,a,p,t] );

subject to chargingstation_c3{uc in UnitsOfType['EV_charger'],p in Period,t in Time[p]}:
Units_supply['Electricity',uc,p,t] * (1/EV_eff_di)  = sum {u in UnitsOfType['EV']}(V2C[uc,u,p,t] );			

subject to chargingstation_c4{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_demand[u,p,t]  = sum {uc in UnitsOfType['EV_charger']}(C2V[uc,u,p,t] );	

subject to chargingstation_c5{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_supply[u,p,t]  = sum {uc in UnitsOfType['EV_charger']}(V2C[uc,u,p,t] );	

subject to chargingstation_c6{a in Activities,p in Period,t in Time[p]}:
EV_supply_ext[a,p,t]  = sum {uc in UnitsOfType['EV_charger']}(C2A[uc,a,p,t] );

subject to chargingstation_capacity{uc in UnitsOfType['EV_charger']}:
Units_Mult[uc] = EV_charger_Power[uc] * n_chargers[uc];  #kWh

#--Cyclic
subject to EV_EB_cyclic1{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * EV_plugged_out[u,p,t];


subject to EV_EB_cyclic2{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * (1-EV_plugged_out[u,p,t]) - EV_supply_travel[u,p,t] +
											(EV_demand[u,p,t] - EV_supply[u,p,t])*dt[p];


#-----------------------------------------------------------------------------------------------------------------------	
	
