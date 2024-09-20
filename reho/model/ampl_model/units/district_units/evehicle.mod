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
param n_EVtotperhab default 1.5; #1.5; # 1.1;
param n_EV_max{u in UnitsOfType['EV']} := n_EVperhab[u] * Population; 
param n_EVtot_max := n_EVtotperhab * Population; 
param ff_EV{u in UnitsOfType['EV']} default 1.56; # [4]
param EV_plugged_out{u in UnitsOfType['EV'], p in Period, t in Time[p]} default 0.15;	# initialized through the function generate_EV_plugged_out_profiles_district
param EV_plugging_in{u in UnitsOfType['EV'], p in Period, t in Time[p]} default 0.15;	# initialized through the function generate_EV_plugged_out_profiles_district
param tau_relaxation_charging_profile default 0.03;
param EV_activity{a in Activities,u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}; # initialized through the function generate_mobility_parameters
param min_share_EV default 0;
param max_share_EV default 1; # [4] G 3.3.1.6 : share of cars is 66 %
param max_daily_time_spend_travelling{u in UnitsOfType['EV']} default 0.9; # usually a car spends 1h per day on the move - source : Timo

# computed parameters to calculate the variation between EV_E_stored (plug_in and plug_out) depending on EV_plugged_out
param storedOut2Out{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := 
	if EV_plugged_out[u,p,prev(t,Time[p])] = 0 then
		1 
	else
		min(1,EV_plugged_out[u,p,t]/EV_plugged_out[u,p,prev(t,Time[p])]);
param storedIn2In{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := 
	if EV_plugged_out[u,p,prev(t,Time[p])] = 1 then
		1
	else
		min(1,(1-EV_plugged_out[u,p,t])/(1-EV_plugged_out[u,p,prev(t,Time[p])]));
param storedIn2Out{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := 
	if EV_plugged_out[u,p,prev(t,Time[p])] = 1 then
		0
	else
		max(0,1-(1-EV_plugged_out[u,p,t])/(1-EV_plugged_out[u,p,prev(t,Time[p])]));
param storedOut2In{u in UnitsOfType['EV'], p in Period, t in Time[p] diff {first(Time[p])}} := 
	if EV_plugged_out[u,p,prev(t,Time[p])] = 0 then
		0
	else
		max(0,1-EV_plugged_out[u,p,t]/EV_plugged_out[u,p,prev(t,Time[p])]);

# Technical caracteriques
param EV_limit_ch default 0.8;				#-		[2]
param EV_limit_di default 0.2;				#-		[1]
param EV_efficiency default 0.99992;		#-		[1]
param EV_capacity default 70;				#kWh 	[5] and [6]
param EV_mobeff default 6; 					#km/kWh

# charging stations
param EV_charger_Power{uc in UnitsOfType['EVcharging']} default 7;			#kW	 	[5] and [7]
param EV_eff_ch default 0.9;				#-		[1] both charging station efficiency and battery efficiency
param EV_eff_di default 0.9;				#-		[1]
param charging_externalload{a in Activities, p in Period, t in Time[p]} default 0; #kWh
param externalload_sellingprice{ p in PeriodStandard, t in Time[p]} default 0;

# EV batteries charging outside the district
param Out_charger_Power{d in Districts} default 7; # kW - describes the mean charger power of the overall town (sum of districts)
param frequency_outcharging{a in Activities} default 1; # - not all activities provide the same chance to have a charging station (ex : if you go hiking there's probably no charging station)
param share_district_activity{a in Activities, d in Districts} default 0; # to describe the distribution of EVs plugged out in the other disctricts : default 0 means that there is no interaction with other districts = run as standalone
param outside_charging_price{d in Districts, p in PeriodStandard, t in Time[p]} default Cost_supply_network["Electricity",p,t];

# ----------------------------------------- VARIABLES ---------------------------------------
var n_vehicles{u in UnitsOfType['EV']} integer >= 0;
var EV_E_stored{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_E_stored_plug_out{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_E_stored_plug_in{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_V2V{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_E_mob{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;

# charging stations
var n_chargingpoints{uc in UnitsOfType['EVcharging']} integer >= 0;
var EV_E_charging{u in UnitsOfType['EV'],p in Period,t in Time[p]} >=0;
var coeff_supply{u in UnitsOfType['EV'],p in Period} >= 0;
var EV_E_supply{u in UnitsOfType['EV'],p in Period,t in Time[p]} >=0;
var C2V{uc in UnitsOfType['EVcharging'],u in UnitsOfType['EV'],p in Period,t in Time[p]}>= 0 ;
var V2C{uc in UnitsOfType['EVcharging'],u in UnitsOfType['EV'],p in Period,t in Time[p]}>= 0 ;

# EV batteries charging outside the district
var EV_E_charged_outside{a in Activities, d in Districts, u in UnitsOfType['EV'], p in Period, t in Time[p]} >= 0; # kWh
var C2A{uc in UnitsOfType['EVcharging'],a in Activities,p in Period,t in Time[p]}>= 0 ;


# ---------------------------------------- CONSTRAINTS ---------------------------------------
#--Energy balance
subject to EV_EB_c1{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency * (storedOut2Out[u,p,t]*EV_E_stored_plug_out[u,p,prev(t,Time[p])] + storedIn2Out[u,p,t]*EV_E_stored_plug_in[u,p,prev(t,Time[p])]);

subject to EV_EB_c2{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency * (storedIn2In[u,p,t]*EV_E_stored_plug_in[u,p,prev(t,Time[p])] + storedOut2In[u,p,t]*EV_E_stored_plug_out[u,p,prev(t,Time[p])]) -
							EV_E_mob[u,p,t] - EV_V2V[u,p,t] * (1 - EV_eff_ch * EV_eff_di) +
							(EV_E_charging[u,p,t]  - EV_E_supply[u,p,t]) * dt[p];



subject to EV_EB_c3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] =  EV_E_stored_plug_in[u,p,t] + EV_E_stored_plug_out[u,p,t];

subject to EV_EB_upper_bound1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] <= EV_capacity * n_vehicles[u];

subject to EV_EB_upper_bound2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] <= EV_capacity * n_vehicles[u];

subject to EV_EB_upper_bound3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] <= EV_capacity * n_vehicles[u];

# subject to EV_V2V_1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
# EV_V2V[u,p,t] >= EV_E_mob[u,p,t] - EV_E_charging[u,p,t]; #question : pq ici il y avait pas le d[t] dans EV_displacement[] * Unit_use * dt ?

subject to EV_chargingconstraint{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
sum {uc in UnitsOfType['EVcharging']}(C2V[uc,u,p,t]/EV_charger_Power[uc]) <= n_vehicles[u] * (1 - EV_plugged_out[u,p,t]);



subject to unidirectional_service{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_supply[u,p,t] = 0;

subject to unidirectional_service2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_V2V[u,p,t] = 0;

# mobility and outside-the-district charging
subject to EV_EB_mobility1{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= n_vehicles[u]* EV_activity['travel',u,p,t] * Mode_Speed[u]; 

subject to EV_EB_mobility2{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_E_mob[u,p,t] = Units_supply['Mobility',u,p,t]/ ff_EV[u] / EV_mobeff  - sum{d in Districts}(sum{a in Activities}(EV_E_charged_outside[a,d,u,p,t]));

# EV_E_mob[u,p,t] = sum {i in Time[p] : i<=t}(Units_supply['Mobility',u,p,i]/ ff_EV[u] / EV_mobeff  - sum{d in Districts}(sum{a in Activities}(EV_E_charged_outside[a,d,u,p,i])) ) * EV_plugging_in[u,p,t]; # pkm * car/pers * kWh/km * share of EV coming back

subject to EV_supplyprofile1{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_E_charging[u,p,t] <= coeff_supply[u,p] * EV_plugging_in[u,p,t] * (1 + tau_relaxation_charging_profile); 

subject to EV_supplyprofile2{u in UnitsOfType['EV'],p in PeriodStandard,t in Time[p]}:
EV_E_charging[u,p,t] >= coeff_supply[u,p] * EV_plugging_in[u,p,t] * (1 - tau_relaxation_charging_profile); 

subject to outside_charging_c1{a in Activities,d in Districts, u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}:
EV_E_charged_outside[a,d,u,p,t] <= EV_activity[a,u,p,t]* share_district_activity[a,d] * frequency_outcharging[a] * n_vehicles[u] * Out_charger_Power[d];

subject to outside_charging_c2{d in Districts, u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}:
EV_E_charged_outside["travel",d,u,p,t] <=0; # During the travel activity, EV can provide pkm, but they do not have charging opportunities. 

# subject to outside_charging_c3{d in Districts, u in UnitsOfType['EV'], p in PeriodStandard, t in Time[p]}:
# EV_E_charged_outside["leisure",d,u,p,t] <=0; 																# for testing


subject to outside_charging_costs{ p in PeriodStandard, t in Time[p]}:
ExternalEV_Costs_op[p,t] = sum{d in Districts}( outside_charging_price[d,p,t] *sum {a in Activities} (sum {u in UnitsOfType['EV'] } (EV_E_charged_outside[a,d,u,p,t]))) # 
							- externalload_sellingprice[p,t] *sum {a in Activities}(charging_externalload[a,p,t] ) ;




#--Stock constraints
subject to EV_stock_upperbound1{u in UnitsOfType['EV']}:
n_vehicles[u] <= n_EV_max[u];

subject to EV_stock_upperbound2:
sum{u in UnitsOfType['EV']} (n_vehicles[u]) <= n_EVtot_max;

#--Max share and time of travel
subject to EV_maxshare{p in PeriodStandard}:
sum {u in UnitsOfType['EV'],t in Time[p]}(Units_supply['Mobility',u,p,t]) <= max_share_EV * Population * DailyDist; 

subject to EV_minshare{p in PeriodStandard}:
sum {u in UnitsOfType['EV'],t in Time[p]}(Units_supply['Mobility',u,p,t]) >= min_share_EV * Population * DailyDist; 

subject to EV_timeoftravel{p in Period,u in UnitsOfType['EV']}:
sum {t in Time[p]}(Units_supply['Mobility',u,p,t])/ff_EV[u] /Mode_Speed[u]  <= max_daily_time_spend_travelling[u] * n_vehicles[u] ; 

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
EV_E_stored_plug_out[u,p,t] <= (EV_limit_ch*EV_capacity * n_vehicles[u] + EV_E_mob[u,p,t]) * EV_plugged_out[u,p,t];										#kWh

subject to EV_c6c{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] >= (EV_limit_di*EV_capacity * n_vehicles[u] + EV_E_mob[u,p,t]) * EV_plugged_out[u,p,t];										#kWh
																			#-
	
subject to EV_c7a{u in UnitsOfType['EV']}:
Units_Mult[u] = EV_capacity*n_vehicles[u];  #kWh

#subject to EV_c8{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=4}:
#EV_E_stored[u,p,t] >= EV_limit_ch*EV_capacity*n_vehicles[u];											#kWh

#--Charging_stations
subject to chargingstation_c1{uc in UnitsOfType['EVcharging'],p in Period,t in Time[p]}:
Units_demand['Electricity',uc,p,t] + Units_supply['Electricity',uc,p,t] <= EV_charger_Power[uc] * n_chargingpoints[uc];								#kW

subject to chargingstation_c2{uc in UnitsOfType['EVcharging'],p in Period,t in Time[p]}:
Units_demand['Electricity',uc,p,t] * EV_eff_ch  = sum {u in UnitsOfType['EV']}(C2V[uc,u,p,t])+ sum{a in Activities} (C2A[uc,a,p,t] );

subject to chargingstation_c3{uc in UnitsOfType['EVcharging'],p in Period,t in Time[p]}:
Units_supply['Electricity',uc,p,t] * (1/EV_eff_di)  = sum {u in UnitsOfType['EV']}(V2C[uc,u,p,t] );			

subject to chargingstation_c4{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_charging[u,p,t]  = sum {uc in UnitsOfType['EVcharging']}(C2V[uc,u,p,t] );	

subject to chargingstation_c5{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_supply[u,p,t]  = sum {uc in UnitsOfType['EVcharging']}(V2C[uc,u,p,t] );	

subject to chargingstation_c6{a in Activities,p in Period,t in Time[p]}:
charging_externalload[a,p,t]  = sum {uc in UnitsOfType['EVcharging']}(C2A[uc,a,p,t] );	

subject to chargingstation_capacity{uc in UnitsOfType['EVcharging']}:
Units_Mult[uc] = EV_charger_Power[uc] * n_chargingpoints[uc];  #kWh

#--Cyclic
subject to EV_EB_cyclic1{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * EV_plugged_out[u,p,t];


subject to EV_EB_cyclic2{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * (1-EV_plugged_out[u,p,t]) - EV_E_mob[u,p,t] +
											(EV_E_charging[u,p,t] - EV_E_supply[u,p,t])*dt[p];


#-----------------------------------------------------------------------------------------------------------------------	
	
