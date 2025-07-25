set Actors default {"Owners", "Renters", "Utility"};
set ActorObjective;

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
var C_op_renters_to_utility{h in House} >= 0;
var C_op_renters_to_owners{h in House} >= 0;

subject to Costs_opex_renter1{h in House}:
C_op_renters_to_utility[h] = sum{l in ResourceBalances, f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} (Cost_supply_district[l,f,h] * Grid_supply[l,f,h,p,t] * dp[p] * dt[p] );

subject to Costs_opex_renter2{h in House}:
C_op_renters_to_owners[h] = sum{f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} (Cost_self_consumption[f,h] * PV_self_consummed[f,h,p,t] * dp[p] * dt[p] );

subject to Renter1{h in House}:
renter_expense[h] = C_rent_fix[h] + C_op_renters_to_utility[h] + C_op_renters_to_owners[h];

subject to Rent_fix{h in House, i in House : h != i}:
(C_rent_fix[h] / ERA[h]) <= 1.2 * (C_rent_fix[i] / ERA[i]); 

subject to Rent_fix2{h in House, i in House : h != i}:
(C_rent_fix[h] / ERA[h]) >= 0.8 * (C_rent_fix[i] / ERA[i]);

subject to Renter_noSub{h in House}:
renter_subsidies[h] = 0;

subject to Renter_epsilon{h in House}: #nu_renters
renter_expense[h] - renter_subsidies[h] <= renter_expense_max[h];

subject to obj_fct1:
objective_functions["Renters"] = sum{h in House}(renter_expense[h]);

#--------------------------------------------------------------------------------------------------------------------#
# Utility constraints
#--------------------------------------------------------------------------------------------------------------------#
param utility_profit_min default -1e-6;
var utility_profit;
var C_op_utility_to_owners{h in House};

subject to Utility1{h in House}: 
C_op_utility_to_owners[h] = sum{l in ResourceBalances, f in FeasibleSolutions, p in PeriodStandard, t in Time[p]} (Cost_demand_district[l,f,h] * Grid_demand[l,f,h,p,t] * dp[p] * dt[p]);

subject to Utility2:
utility_profit = sum{h in House} (C_op_renters_to_utility[h] - C_op_utility_to_owners[h]) - Costs_op - tau * sum{u in Units} Costs_Unit_inv[u] - Costs_rep;

subject to Utility_epsilon: # nu_utility
utility_profit >= utility_profit_min;

subject to obj_fct2:
objective_functions["Utility"] = - utility_profit;

#--------------------------------------------------------------------------------------------------------------------#
# Owners constraints
#--------------------------------------------------------------------------------------------------------------------#
param Costs_House_upfront_m2_MP default 7759;
param Costs_House_upfront{h in House} := ERA[h]* Costs_House_upfront_m2_MP;
param Costs_House_yearly{h in House} := Costs_House_upfront[h]/100 + Costs_House_upfront[h] * i_rate * (0.13/(1-(1+i_rate)^(-15)) + 0.67/(1-(1+i_rate)^(-70))) - Costs_House_upfront[h] * (1/15+1/70);
param owner_PIR_min default 0;
param owner_PIR_max default 0.3;

var owner_profit{h in House};

#Scenario 2 & 2.1 & 3 (Owner_Sub_bigM_ub)
subject to Owner_Link_Subsidy_to_renovation{h in House}:
owner_subsidies[h] <= 1e10 * is_ins[h];

subject to Owner_profit{h in House}:
owner_profit[h] = C_rent_fix[h] + C_op_renters_to_owners[h] + C_op_utility_to_owners[h] - Costs_House_inv[h] - Costs_House_yearly[h];

#Scenario 2.1 (Owner2)
subject to Owner_profit_max_PIR{h in House}:
owner_profit[h] <= owner_PIR_max * (Costs_House_inv[h] + Costs_House_upfront[h]);

subject to Owner_epsilon{h in House}: #nuH_owner
owner_profit[h] + owner_subsidies[h] >= owner_PIR_min * (Costs_House_inv[h] + Costs_House_upfront[h]); #owner_profit_min[h];

subject to Owner_noSub{h in House}:
owner_subsidies[h] = 0;

subject to obj_fct3:
objective_functions["Owners"] = - sum{h in House}(owner_profit[h]);


#--------------------------------------------------------------------------------------------------------------------#
# Objectives
#--------------------------------------------------------------------------------------------------------------------#

subject to penalty_actors_obj_fct:
penalty_actors = sum{a in Actors}(objective_functions[a]);

minimize TOTEX_actor:
sum {a in ActorObjective} objective_functions[a] + penalty_ratio * (Costs_inv + Costs_op + sum{h in House}(renter_subsidies[h] + owner_subsidies[h]));
# - sum{h in House} (C_rent_fix[h] + C_op_renters_to_owners[h] + C_op_utility_to_owners[h] - Costs_House_inv[h] + owner_subsidies[h]);
# - (sum{h in House} (C_op_renters_to_utility[h] - C_op_utility_to_owners[h]) - Costs_op - tau * sum{u in Units} Costs_Unit_inv[u] - Costs_rep);
