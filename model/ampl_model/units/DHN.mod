######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---DHN model with costs and mass flows
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param factor_distance_house{h in House};
param area_district default 1e5; # m2
param n_house := sum{h in House}(1);
param distance_buildings := ((area_district/n_house)^(1/2) * 0.4 * (n_house-1)) / n_house;

param velocity default 1; # m/s
param density default 827; # kg/m3, https://www.engineeringtoolbox.com
param sizing_factor := 4 / (3.14 * velocity * density);
param delta_enthalpy default 179.5; # kJ/kg default is CO2 network, https://www.engineeringtoolbox.com

param flowrate_out{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := Grid_demand["Heat",f,h,p,t] / delta_enthalpy;
param flowrate_in{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := Grid_supply["Heat",f,h,p,t] / delta_enthalpy;
param diameter_out{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := (sizing_factor * flowrate_out[f,h,p,t])^(1/2) ;
param diameter_in{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} := (sizing_factor * flowrate_in[f,h,p,t])^(1/2) ;

param cinv1_dhn default 5670;	# chf/m2, Raluca-Ancuta SUCIU thesis
param cinv2_dhn default 613; # chf/m, Raluca-Ancuta SUCIU thesis
#param enforce_DHN default 0;

var diameter_max{h in House} >=0;
var DHN_inv >=0;
var connection_house{h in House} binary;
#var flowrate_max{h in House} >=0;

subject to DHN_size_1{h in House, p in Period,t in Time[p]}:
diameter_max[h] >= sum{f in FeasibleSolutions} (diameter_out[f,h,p,t] * lambda[f,h]);

subject to DHN_size_2{h in House, p in Period,t in Time[p]}:
diameter_max[h] >= sum{f in FeasibleSolutions} (diameter_in[f,h,p,t] * lambda[f,h]);

subject to DHN_size_3{h in House}:
connection_house[h] >= diameter_max[h];

#subject to DHN_size_4{h in House}:
#diameter_max[h] >= enforce_DHN;

#subject to DHN_size_5{h in House}:
#connection_house[h] >= enforce_DHN; # if enforce_DHN not 0, connection_house enforced to 1

subject to DHN_capex{h in House}:
DHN_inv_house[h] = tau * distance_buildings *  (cinv1_dhn * diameter_max[h] * factor_distance_house[h] + connection_house[h] * cinv2_dhn);

subject to DHN_capex2:
DHN_inv = sum{h in House} DHN_inv_house[h];

#subject to NPV_DHN:
#DHN_inv <= sum{p in PeriodStandard, t in Time[p]}(Cost_supply_network["Heat",p,t]*Network_supply["Heat",p,t] - Cost_demand_network["Heat",p,t]*Network_demand["Heat",p,t]); 

#subject to DHN_max_heat{p in Period,t in Time[p]}:
#sum{f in FeasibleSolutions, h in House} (flowrate_in[f,h,p,t] * lambda[f,h]) = Network_supply["Heat",p,t] / ( delta_enthalpy * dp[p] * dt[p] ) ;

#var max_grid{f in FeasibleSolutions, h in House, p in Period,t in Time[p]} >=0;

#subject to DHN_2{f in FeasibleSolutions, h in House, p in PeriodStandard,t in Time[p]}:
#Grid_supply["Heat",f,h,p,t] <= max_grid[f,h,p,t];

#subject to DHN_3{p in PeriodStandard,t in Time[p]}:
#Network_supply["Heat",p,t] <= sum{f in FeasibleSolutions, h in House} max_grid[f,h,p,t];


#subject to DHN_max_heat2{p in Period,t in Time[p], h in House}:
#sum{f in FeasibleSolutions} (flowrate_in[f,h,p,t] * lambda[f,h]) >= sum{f in FeasibleSolutions} (Grid_supply["Heat",f,h,p,t]* lambda[f,h]) / delta_enthalpy  ;
