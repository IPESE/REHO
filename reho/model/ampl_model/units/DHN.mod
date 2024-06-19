######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# District heating network - Model with costs and mass flows
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

set House_ID ordered;
param area_district default 1e5; # m2
param n_house := sum{h in House}(1);
param distance_buildings := ((area_district/n_house)^(1/2) * 0.4 * (n_house-1)) / n_house;

param velocity default 1; # m/s
param density default 827; # kg/m3
param sizing_factor := 4 / (3.14 * velocity * density);
param delta_enthalpy default 179.5; # kJ/kg (default is CO2 network)

param flowrate_out{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := Grid_demand["Heat",f,h,p,t] / delta_enthalpy;
param flowrate_in{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := Grid_supply["Heat",f,h,p,t] / delta_enthalpy;
param diameter_out{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := (sizing_factor * flowrate_out[f,h,p,t])^(1/2) ;
param diameter_in{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := (sizing_factor * flowrate_in[f,h,p,t])^(1/2) ;

param diameter_k_in{f in FeasibleSolutions, i in House_ID, p in Period,t in Time[p]} := 
	( sizing_factor * sum{j in House_ID: j>=i} flowrate_in[f,"Building"&j,p,t])^0.5;

param diameter_k_out{f in FeasibleSolutions, i in House_ID, p in Period,t in Time[p]} := 
	( sizing_factor * sum{j in House_ID: j>=i} flowrate_out[f,"Building"&j,p,t])^0.5;

param cinv1_dhn default 5670;	# CHF/m2
param cinv2_dhn default 613;	# CHF/m

var diameter_max{h in House} >=0;
var diameter_k{h in House} >=0;
var flowrate_max{h in House} >=0;
var DHN_inv >=0;
var connection_house{h in House} binary;


subject to DHN_size_1{h in House, p in Period,t in Time[p]}:
diameter_max[h] >= sum{f in FeasibleSolutions} (diameter_out[f,h,p,t] * lambda[f,h]);

subject to DHN_size_2{h in House, p in Period,t in Time[p]}:
diameter_max[h] >= sum{f in FeasibleSolutions} (diameter_in[f,h,p,t] * lambda[f,h]);

subject to DHN_size_3{i in House_ID, p in Period,t in Time[p]}:
diameter_k["Building"&i] >= sum{f in FeasibleSolutions} (diameter_k_in[f,i,p,t] * lambda[f,"Building"&i]);

subject to DHN_size_4{i in House_ID, p in Period,t in Time[p]}:
diameter_k["Building"&i] >= sum{f in FeasibleSolutions} (diameter_k_out[f,i,p,t] * lambda[f,"Building"&i]);

subject to DHN_size_5{h in House}:
connection_house[h] >= diameter_max[h];

subject to DHN_size_6{h in House, p in Period,t in Time[p]}:
flowrate_max[h] >= sum{f in FeasibleSolutions} (flowrate_out[f,h,p,t] * lambda[f,h]);

subject to DHN_size_7{h in House, p in Period,t in Time[p]}:
flowrate_max[h] >= sum{f in FeasibleSolutions} (flowrate_in[f,h,p,t] * lambda[f,h]);


subject to DHN_capex{h in House}:
DHN_inv_house[h] = tau * distance_buildings * (cinv1_dhn * diameter_k[h] + connection_house[h] * cinv2_dhn);

subject to DHN_capex2:
DHN_inv = sum{h in House} DHN_inv_house[h];
