######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---EV MODEL
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
param n_vehicles default sum{h in House}(1);
param EV_eff_ch default 0.9;				#-	[1] both charging station efficiency and battery efficiency
param EV_eff_di default 0.9;				#-	[1]
param EV_limit_ch default 0.8;				#-	[2]
param EV_limit_di default 0.2;				#-	[1]
param EV_efficiency default 0.99992;		#-	[1]
param EV_charger_Power default 7;			#kW	 	[5] and [7]
param EV_capacity default 70;		#kWh 	[5] and [6]
param EV_plugged_out{p in Period, t in Time[p]} default 0.15;	# -
param EV_plugging_in{p in Period, t in Time[p]} default 0.15;	# -
param normalization_factor :=  max{p in PeriodStandard} ( sum{t in Time[p]}EV_plugging_in[p,t]);

param EV_displacement_init{p in Period} := 
		if p in PeriodStandard then 23.8 * 1.56 / 6 / normalization_factor	# km/person/day * person/car / km/kWh / normalisation factor 	[4] p.30, 32 and [5] 
		else  0.0;

param EV_displacement{u in UnitsOfType['EV'],p in Period, t in Time[p]} := EV_displacement_init[p] * EV_plugging_in[p,t] * n_vehicles;	#kW
	
# ----------------------------------------- VARIABLES ---------------------------------------
var EV_E_stored{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_E_stored_plug_out{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_E_stored_plug_in{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
var EV_V2V{u in UnitsOfType['EV'],p in Period,t in Time[p]} >= 0;
# ---------------------------------------- CONSTRAINTS ---------------------------------------
#--Energy balance
subject to EV_EB_c1{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency * EV_E_stored[u,p,prev(t,Time[p])] * EV_plugged_out[p,t];

subject to EV_EB_c2{u in UnitsOfType['EV'],p in Period,t in Time[p] diff {first(Time[p])}}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency * EV_E_stored[u,p,prev(t,Time[p])] * (1-EV_plugged_out[p,t]) -
							EV_displacement[u,p,t] * Units_Use[u] * dt[p] - EV_V2V[u,p,t] * (1 - EV_eff_ch * EV_eff_di) +
							(EV_eff_ch * Units_demand['Electricity',u,p,t]  - (1/EV_eff_di) * Units_supply['Electricity',u,p,t]) * dt[p];

subject to EV_EB_c3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] =  EV_E_stored_plug_in[u,p,t] + EV_E_stored_plug_out[u,p,t];


subject to EV_EB_upper_bound1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] <= EV_capacity * n_vehicles * Units_Use[u];

subject to EV_EB_upper_bound2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] <= EV_capacity * n_vehicles * Units_Use[u];

subject to EV_EB_upper_bound3{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] <= EV_capacity * n_vehicles * Units_Use[u];

subject to EV_V2V_1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_V2V[u,p,t] >= EV_displacement[u,p,t] * Units_Use[u] - EV_eff_ch * Units_demand['Electricity',u,p,t];

subject to unidirectional_service{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = 0;

subject to unidirectional_service2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_V2V[u,p,t] = 0;



#--SoC constraints
subject to EV_c1{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] <= EV_charger_Power * n_vehicles * Units_Use[u];								#kW

subject to EV_c2{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= EV_charger_Power * n_vehicles * Units_Use[u];								#kW


subject to EV_c5a{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] <= EV_limit_ch * EV_capacity * n_vehicles * Units_Use[u];											#kWh

subject to EV_c6a{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored[u,p,t] >= EV_limit_di * EV_capacity * n_vehicles * Units_Use[u];											#kWh


subject to EV_c5b{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] <= EV_limit_ch*EV_capacity*n_vehicles*Units_Use[u]* (1-EV_plugged_out[p,t]);											#kWh

subject to EV_c6b{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_in[u,p,t] >= EV_limit_di*EV_capacity*n_vehicles*Units_Use[u]* (1-EV_plugged_out[p,t]);											#kWh
	
	
subject to EV_c5c{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] <= (EV_limit_ch*EV_capacity*Units_Use[u] + EV_displacement_init[p]) * n_vehicles * EV_plugged_out[p,t];											#kWh

subject to EV_c6c{u in UnitsOfType['EV'],p in Period,t in Time[p]}:
EV_E_stored_plug_out[u,p,t] >= (EV_limit_di*EV_capacity*Units_Use[u] + EV_displacement_init[p]) * n_vehicles * EV_plugged_out[p,t];										#kWh
																			#-
	
subject to EV_c7a{u in UnitsOfType['EV']}:
Units_Mult[u] >= EV_capacity*n_vehicles*Units_Use[u];

subject to EV_c7b{u in UnitsOfType['EV']}:
Units_Mult[u] <= (EV_capacity*n_vehicles +1)*Units_Use[u];

#subject to EV_c8{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=4}:
#EV_E_stored[u,p,t] >= EV_limit_ch*EV_capacity*n_vehicles*Units_Use[u];											#kWh

#--Cyclic
subject to EV_EB_cyclic1{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_out[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * EV_plugged_out[p,t];


subject to EV_EB_cyclic2{u in UnitsOfType['EV'],p in Period,t in Time[p]:t=first(Time[p])}:
EV_E_stored_plug_in[u,p,t] = EV_efficiency*EV_E_stored[u,p,last(Time[p])] * (1-EV_plugged_out[p,t]) - EV_displacement[u,p,t]*Units_Use[u]*dt[p] +
											(EV_eff_ch*Units_demand['Electricity',u,p,t]  - (1/EV_eff_di)*Units_supply['Electricity',u,p,t])*dt[p];


#-----------------------------------------------------------------------------------------------------------------------	
	