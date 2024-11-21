set Actors default {"Owners", "Renters", "Utility"};
set ActorObjective;

# Risk factor (listed but unused)
param risk_factor default 0;

# Energy tariffs
var Cost_supply_district{l in ResourceBalances, f in FeasibleSolutions, h in House};
var Cost_demand_district{l in ResourceBalances, f in FeasibleSolutions, h in House};
var Cost_self_consumption{f in FeasibleSolutions, h in House};

subject to size_cstr1{l in ResourceBalances, f in FeasibleSolutions, h in House}:            
   Cost_demand_cst[l] *lambda[f,h] <= Cost_supply_district[l,f,h];

subject to size_cstr2{l in ResourceBalances, f in FeasibleSolutions, h in House}:            
   Cost_supply_district[l,f,h] <= Cost_supply_cst[l] *lambda[f,h];

subject to size_cstr3{l in ResourceBalances, f in FeasibleSolutions, h in House}:            
   Cost_demand_cst[l] * lambda[f,h] <= Cost_demand_district[l,f,h];

subject to size_cstr4{l in ResourceBalances, f in FeasibleSolutions, h in House}:           
   Cost_demand_district[l,f,h] <= Cost_supply_cst[l] *lambda[f,h];

subject to size_cstr5{l in ResourceBalances, f in FeasibleSolutions, h in House: l="Electricity"}:            
   Cost_demand_cst[l] *lambda[f,h] <= Cost_self_consumption[f,h];

subject to size_cstr6{l in ResourceBalances, f in FeasibleSolutions, h in House: l="Electricity"}:           
   Cost_self_consumption[f,h] <= Cost_supply_cst[l] *lambda[f,h];

# Self-consumption
param PV_prod{f in FeasibleSolutions, h in House, p in Period, t in Time[p]};
param PV_self_consummed{f in FeasibleSolutions, h in House, p in Period, t in Time[p]} :=  PV_prod[f,h,p,t] - Grid_demand["Electricity",f,h,p,t];

#--------------------------------------------------------------------------------------------------------------------#
# Renters constraints
#--------------------------------------------------------------------------------------------------------------------#
var objective_functions{a in Actors};

param renter_expense_max{h in House} default 1e10; 
var renter_expense{h in House};
var C_rent_fix{h in House} >= 0;
var C_op_renters_to_utility{h in House};
var C_op_renters_to_owners{h in House};
# var subsidies{h in House} >= 0;

subject to Costs_opex_renter1{h in House}:
C_op_renters_to_utility[h] = sum{l in ResourceBalances, f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} ( Cost_supply_district[l,f,h] * Grid_supply[l,f,h,p,t] * dp[p] * dt[p] );

subject to Costs_opex_renter2{h in House}:
C_op_renters_to_owners[h] = sum{l in ResourceBalances, f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} ( Cost_self_consumption[f,h] * PV_self_consummed[f,h,p,t] * dp[p] * dt[p] );

subject to Renter1{h in House}:
renter_expense[h] = C_rent_fix[h] + C_op_renters_to_utility[h] + C_op_renters_to_owners[h] - renter_subsidies[h] ;

subject to Rent_fix{h in House, i in House : h != i}:
(C_rent_fix[h] / ERA[h]) <= 1.15 * (C_rent_fix[i] / ERA[i]); 

subject to Rent_fix2{h in House, i in House : h != i}:
(C_rent_fix[h] / ERA[h]) >= 0.85 * (C_rent_fix[i] / ERA[i]);

subject to Renter_subsidies_interval{h in House}:
renter_subsidies[h] <= 400 * ERA[h];

subject to Renter_epsilon{h in House}: #nu_renters
# renter_expense[h] <= renter_expense_max[h];
renter_expense[h] <= renter_expense_max[h];    

subject to obj_fct1:
objective_functions["Renters"] = sum{h in House}(renter_expense[h]);

#--------------------------------------------------------------------------------------------------------------------#
# Utility constraints
#--------------------------------------------------------------------------------------------------------------------#
param utility_portfolio_min default -1e6;
var utility_portfolio;
var C_op_utility_to_owners{h in House};

subject to Utility1{h in House}: 
C_op_utility_to_owners[h] = sum{l in ResourceBalances, f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} (Cost_demand_district[l,f,h] * Grid_demand[l,f,h,p,t] * dp[p] * dt[p] );

subject to Utility2:
utility_portfolio = sum{h in House} (C_op_renters_to_utility[h] - C_op_utility_to_owners[h]) - Costs_op - tau * sum{u in Units} Costs_Unit_inv[u] - Costs_rep;

subject to Utility_epsilon: # nu_utility
utility_portfolio >= utility_portfolio_min;

subject to obj_fct2:
objective_functions["Utility"] = - utility_portfolio;

#--------------------------------------------------------------------------------------------------------------------#
# Owners constraints
#--------------------------------------------------------------------------------------------------------------------#
param owner_portfolio_min default -1e6;
var owner_portfolio{h in House};
var owner_subsidies{h in House};

subject to Owner_Sub{h in House}:
owner_subsidies[h] = 0;
   
subject to Owner1{h in House}:
owner_portfolio[h] = C_rent_fix[h] + C_op_renters_to_owners[h] + C_op_utility_to_owners[h] - Costs_House_inv[h] - ERA[h]* 6000/((1-(1.02^(-50)))/(0.02)); #sub.

subject to Owner_epsilon: #nu_owner
sum{h in House} owner_portfolio[h] >= 0;
#sum{h in House} (owner_portfolio[h] + owner_subsidies[h]) >= owner_portfolio_min; 

subject to obj_fct3:
objective_functions["Owners"] = - sum{h in House} owner_portfolio[h];


#--------------------------------------------------------------------------------------------------------------------#
# Objectives
#--------------------------------------------------------------------------------------------------------------------#
minimize TOTEX_bui:
sum {a in ActorObjective} objective_functions[a];
# - sum{h in House} (C_rent_fix[h] + C_op_renters_to_owners[h] + C_op_utility_to_owners[h] - Costs_House_inv[h] + owner_subsidies[h]);
# - (sum{h in House} (C_op_renters_to_utility[h] - C_op_utility_to_owners[h]) - Costs_op - tau * sum{u in Units} Costs_Unit_inv[u] - Costs_rep);