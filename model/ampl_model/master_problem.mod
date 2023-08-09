# -------------------------------------------------------------------------------------------------------------------------
# Renewable Energy Hub Optimizer (REHO) is an open-source energy model suitable for the optimization of energy systems at building-scale or district-scale.
# It considers simultaneously the optimal design as well as optimal scheduling of capacities.
# It allows to investigate the deployment of energy conversion and energy storage capacities to ensure the energy balance of a specified territory,
# through multi-objective optimization and KPIs parametric studies. It is based on an hourly resolution.
# 
# Copyright (C) <2021-2023> <Ecole Polytechnique Fédérale de Lausanne (EPFL), Switzerland>
# 
# Licensed under the Apache License, Version0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
# Description and complete License: see LICENSE file.
# -------------------------------------------------------------------------------------------------------------------------
# 
# Version 1.0 of the model.
# See documentation : https://reho.readthedocs.io/en/main/
# See repo :  https://github.com/Renewable-Energy-Hub-Optimizer


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---# General Sets & Parameter
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# Sets
set Layers;          # Set of layers
set LayerTypes;      # Type of layer (HeatCascade, MassBalance, ...)
set LayersOfType{LayerTypes} within Layers;
set ResourceBalances := if (exists{t in LayerTypes} t = 'ResourceBalance') then ({l in LayersOfType["ResourceBalance"]}) else ({});

set UnitTypes default {'Battery', 'EV'};
set Units default {'Battery_district', 'EV_district'};              # Set of units
set UnitsOfType{UnitTypes} within Units default {'Battery_district', 'EV_district'};
set UnitsOfLayer{Layers} within Units;

set House;
set FeasibleSolutions ordered;

set Period;				# Set of periods (days)
set PeriodStandard; # TODO set time as function of period as in model.mod
set PeriodExtrem := {Period diff PeriodStandard};

param TimeStart default 1;
param TimeEnd{p in Period};
set Time{p in Period} := {TimeStart .. TimeEnd[p]} ordered;

param dt{p in Period} default 1;		#h
param dp{p in Period}default 1;			#days

param Area_tot default 100;
param ERA{h in House} default 100;

param n_years default 20;                                           #yr
param i_rate default 0.02;                                          #-
param tau := i_rate*(1+i_rate)^n_years/(((1+i_rate)^n_years)-1);    #-




######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---# convexity constraints
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################


# variables
var lambda{f in FeasibleSolutions, h in House} >= 0;
var lambda_binary{f in FeasibleSolutions, h in House} binary;


subject to convexity_1{h in House}: #mu
sum{f in FeasibleSolutions}(lambda[f,h]) = 1;

subject to convexity_2{f in FeasibleSolutions, h in House}:
lambda[f,h] <=1;

subject to convexity_binary{f in FeasibleSolutions, h in House}:
lambda[f,h] = lambda_binary[f,h];




######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---Network BALANCES - attention only electricity layer!
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
param Grid_supply{l in ResourceBalances, f in FeasibleSolutions, h in House, p in Period, t in Time[p]};
param Grid_demand{l in ResourceBalances, f in FeasibleSolutions, h in House, p in Period, t in  Time[p]};
param TransformerCapacity{l in ResourceBalances} default 1e8;         #kW
param Grids_flowrate{l in ResourceBalances, h in House} default 1e9;
param Grid_usage_max_demand default 0;
param Grid_usage_max_supply default 0;

param Units_flowrate_in{l in ResourceBalances, u in Units}  >=0 default 0;
param Units_flowrate_out{l in ResourceBalances, u in Units} >=0 default 0;

var Units_supply{l in ResourceBalances, u in Units, p in Period, t in Time[p]} >= 0, <= Units_flowrate_out[l,u];
var Units_demand{l in ResourceBalances, u in Units,  p in Period, t in Time[p]} >= 0, <= Units_flowrate_in[l,u];

var Network_supply {l in ResourceBalances, p in Period, t in Time[p]} >= 0 , <=1e9;
var Network_demand{l in ResourceBalances, p in Period, t in Time[p]} >= 0 , <=1e9;
var Network_supply_GWP {l in ResourceBalances, p in Period, t in Time[p]} >= 0;
var Network_demand_GWP{l in ResourceBalances, p in Period, t in Time[p]} >= 0;

var Profile_grid{l in ResourceBalances, p in Period,t in Time[p]}  >= -1e2*Area_tot,<= 1e2*Area_tot;   #kW
var Profile_house{l in ResourceBalances, h in House,p in Period,t in Time[p]} >= -1e2*ERA[h],<= 1e2*ERA[h];                                                            #kW


# model constraints
subject to complicating_cst{l in ResourceBalances, p in Period,t in Time[p]}: #pi_c
   Network_supply[l,p,t] - Network_demand[l,p,t]   =  ( sum{f in FeasibleSolutions, h in House}(lambda[f,h] *(Grid_supply[l,f,h,p,t]-Grid_demand[l,f,h,p,t])) +sum {r in Units} Units_demand[l,r,p,t]-sum {b in Units} Units_supply[l,b,p,t])* dp[p] * dt[p];


subject to complicating_cst_GWP{l in ResourceBalances, p in Period, t in Time[p]}: #pi_g
   Network_supply_GWP[l,p,t] - Network_demand_GWP[l,p,t]   =  ( sum{f in FeasibleSolutions, h in House}(lambda[f,h] *(Grid_supply[l,f,h,p,t]-Grid_demand[l,f,h,p,t])) +sum {r in Units} Units_demand[l,r,p,t]-sum {b in Units} Units_supply[l,b,p,t])* dp[p] * dt[p];


subject to TOTAL_profile_c1{l in ResourceBalances, p in Period,t in Time[p]}:
Profile_grid[l,p,t] =  sum{f in FeasibleSolutions, h in House} ( (Grid_supply[l,f,h,p,t] - Grid_demand[l,f,h,p,t]) * lambda[f,h])
;

subject to TOTAL_profile_c2{l in ResourceBalances, h in House,p in Period,t in Time[p]}:
Profile_house[l,h,p,t] =  sum{f in FeasibleSolutions} ( (Grid_supply[l,f,h,p,t] - Grid_demand[l,f,h,p,t]) * lambda[f,h])
;

#subject to TOTAL_profile_c3{l in ResourceBalances, p in Period,t in Time[p]}:
#Network_supply[l,p,t] <=  sum{f in FeasibleSolutions, h in House} ( Grid_supply[l,f,h,p,t]  * lambda[f,h] * dp[p] * dt[p]) ;

#subject to TOTAL_profile_c4{l in ResourceBalances, p in Period,t in Time[p]}:
#Network_demand[l,p,t] <= sum{f in FeasibleSolutions, h in House} ( Grid_demand[l,f,h,p,t]  * lambda[f,h] * dp[p] * dt[p]) ;

subject to TOTAL_line_c5{l in ResourceBalances, p in Period,t in Time[p]}:
 sum{f in FeasibleSolutions, h in House} (Grid_supply[l,f,h,p,t] * lambda[f,h]) <= sum{h in House} Grids_flowrate[l,h];

subject to TOTAL_line_c6{l in ResourceBalances, p in Period,t in Time[p]}:
 sum{f in FeasibleSolutions, h in House} (Grid_demand[l,f,h,p,t] * lambda[f,h]) <= sum{h in House} Grids_flowrate[l,h];

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---UNITS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################


#-PARAMETERS
param Units_Fmin{u in Units} default 0;
param Units_Fmax{u in Units} default 0;

#-VARIABLES
var Units_Mult{u in Units} <= Units_Fmax[u];                            #var
var Units_Use{u in Units} binary >= 0, default 0;                                       #-


#-CONSTRAINTS
subject to Unit_sizing_c1{u in Units}:
Units_Mult[u] >= Units_Use[u]*Units_Fmin[u];

subject to Unit_sizing_c2{u in Units}:
Units_Mult[u] <= Units_Use[u]*Units_Fmax[u];


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---COSTS + Emissions
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
# parameters
param Costs_inv_rep_SPs{f in FeasibleSolutions, h in House} >= 0;
param Costs_ft_SPs{f in FeasibleSolutions, h in House} >= 0;
param GWP_house_constr_SPs{f in FeasibleSolutions, h in House} >= 0;


#--------------------------------------------------------------------------------------------------------------------#
#-OPERATIONAL EXPENSES
#--------------------------------------------------------------------------------------------------------------------#
#-PARAMETERS
param Cost_supply_cst{l in ResourceBalances} default 0.20;                                # CHF/kWh e.g.
param Cost_demand_cst{l in ResourceBalances} default 0;                                # CHF/kWh e.g.
param Cost_supply_network{l in ResourceBalances, p in Period,t in Time[p]} default Cost_supply_cst[l];  # retail tariff
param Cost_demand_network{l in ResourceBalances, p in Period,t in Time[p]} default Cost_demand_cst[l];  # feed in tariff

#-VARIABLES
var Costs_op;
var Costs_House_op{h in House};

subject to Costs_opex_house{h in House}:
Costs_House_op[h] = sum{f in FeasibleSolutions, l in ResourceBalances, p in PeriodStandard, t in Time[p]} lambda[f,h]*(Cost_supply_network[l,p,t]*Grid_supply[l,f,h,p,t] - Cost_demand_network[l,p,t]*Grid_demand[l,f,h,p,t])* dp[p] * dt[p]; 

subject to Costs_opex:
Costs_op = sum{l in ResourceBalances, p in PeriodStandard, t in Time[p]}(Cost_supply_network[l,p,t]*Network_supply[l,p,t] - Cost_demand_network[l,p,t]*Network_demand[l,p,t]); 


#--------------------------------------------------------------------------------------------------------------------#
#-CAPITAL EXPENSES
#--------------------------------------------------------------------------------------------------------------------#
#-PARAMETERS
param Cost_inv1{u in Units} default 20;                              #CHF
param Cost_inv2{u in Units} default 70;                    #CHF/kWh average from https://www.nrel.gov/docs/fy19osti/73222.pdf
param lifetime {u in Units} default 20;


#-VARIABLES
var Costs_Unit_inv{u in Units} >= -1e-4;
var Costs_inv >= -1e-4;
var Costs_rep >= -1e-4;
var Costs_House_inv{h in House} >= -1e-4;
var Costs_cft >= -1e-4;
var Costs_House_cft{h in House} >= -1e-4;
var Costs_tot;
var DHN_inv_house{h in House} >= 0;

#-CONSTRAINTS
subject to Costs_Unit_capex{u in Units} :
 Costs_Unit_inv[u] = (Units_Use[u]*Cost_inv1[u] + Units_Mult[u]*Cost_inv2[u]);

subject to Costs_Unit_replacement:
Costs_rep= tau* sum{u in Units,n_rep in 1..(n_years/lifetime[u])-1 by 1}( (1/(1 + i_rate))^(n_rep*lifetime[u])*Costs_Unit_inv[u] );


subject to Costs_House_capex{h in House}:
Costs_House_inv[h] =sum{f in FeasibleSolutions} lambda[f,h] * Costs_inv_rep_SPs[f,h] + DHN_inv_house[h];


subject to Costs_capex:
Costs_inv = tau* sum{u in Units} Costs_Unit_inv[u] + Costs_rep + sum{h in House} Costs_House_inv[h];


subject to cft_costs_house{h in House}: 
Costs_House_cft[h] = sum{f in FeasibleSolutions} (lambda[f,h] * Costs_ft_SPs[f,h]);

subject to cft_costs: 
Costs_cft = sum{h in House} Costs_House_cft[h];

subject to total_costs: 
Costs_tot = Costs_op + Costs_inv;


#--------------------------------------------------------------------------------------------------------------------#
#---Emission
#--------------------------------------------------------------------------------------------------------------------#

#-PARAMETERS
param GWP_unit1{u in Units} default 0;
param GWP_unit2{u in Units} default 0;
param GWP_supply_cst{l in ResourceBalances} default 0.17;
param GWP_demand_cst{l in ResourceBalances} default 0.0;                   #-
param GWP_supply{l in ResourceBalances, p in Period,t in Time[p]} default GWP_supply_cst[l];
param GWP_demand{l in ResourceBalances, p in Period,t in Time[p]} default GWP_demand_cst[l];  

#-VARIABLES
var GWP_constr>=0;
var GWP_Unit_constr{u in Units} >= 0;
var GWP_op;
var GWP_House_op{h in House};
var GWP_House_constr{h in House} >=0; 
var GWP_tot;

subject to CO2_construction_unit{u in Units}:
GWP_Unit_constr[u] = (Units_Use[u]*GWP_unit1[u] + Units_Mult[u]*GWP_unit2[u])/lifetime[u];

subject to CO2_construction_house{h in House}:
GWP_House_constr[h] = sum{f in FeasibleSolutions}(lambda[f,h] * GWP_house_constr_SPs[f,h]);

subject to CO2_construction:
GWP_constr = sum {u in Units} GWP_Unit_constr[u] + sum{h in House} GWP_House_constr[h];

subject to Annual_CO2_operation:
GWP_op = sum{l in ResourceBalances, p in PeriodStandard, t in Time[p]} (GWP_supply[l,p,t] * Network_supply_GWP[l,p,t] - GWP_demand[l,p,t] * Network_demand_GWP[l,p,t]);

subject to Annual_CO2_operation_house{h in House}:
GWP_House_op[h] = sum{f in FeasibleSolutions, l in ResourceBalances, p in PeriodStandard, t in Time[p]} lambda[f,h]*(GWP_supply[l,p,t]*Grid_supply[l,f,h,p,t] - GWP_demand[l,p,t]*Grid_demand[l,f,h,p,t])* dp[p] * dt[p]; 

subject to total_GWP: 
GWP_tot = GWP_constr + GWP_op;


set Lca_kpi default {'land_use'};
param lca_kpi_1{k in Lca_kpi, u in Units} default 0;
param lca_kpi_2{k in Lca_kpi, u in Units} default 0;
param lca_kpi_supply_cst{k in Lca_kpi, l in ResourceBalances} default 0.1;
param lca_kpi_demand_cst{k in Lca_kpi, l in ResourceBalances} default 0.0; 
param lca_house_units_SPs{f in FeasibleSolutions, k in Lca_kpi, h in House} default 0;
param lca_kpi_supply{k in Lca_kpi, l in ResourceBalances,p in Period,t in Time[p]} default lca_kpi_supply_cst[k,l];
param lca_kpi_demand{k in Lca_kpi, l in ResourceBalances,p in Period,t in Time[p]} default lca_kpi_demand_cst[k,l];  

var Network_supply_lca {k in Lca_kpi, l in ResourceBalances, p in Period, t in Time[p]} >= 0;
var Network_demand_lca {k in Lca_kpi, l in ResourceBalances, p in Period, t in Time[p]} >= 0;
var lca_op{k in Lca_kpi, l in ResourceBalances} default 0;

var lca_units{k in Lca_kpi, u in Units} default 0;
var lca_house_units{k in Lca_kpi, h in House} default 0;
var lca_inv{k in Lca_kpi} default 0;

var lca_tot{k in Lca_kpi} default 0;
var lca_tot_house{k in Lca_kpi, h in House} default 0;


subject to LU_inv_cst{k in Lca_kpi, u in Units}:
lca_units[k, u] = (Units_Use[u]*lca_kpi_1[k, u] + Units_Mult[u]*lca_kpi_2[k, u])/lifetime[u];

subject to LCA_construction_house{k in Lca_kpi, h in House}:
lca_house_units[k, h] = sum{f in FeasibleSolutions}(lambda[f,h] * lca_house_units_SPs[f,k,h]);

subject to LCA_construction{k in Lca_kpi}:
lca_inv[k] = sum {u in Units} lca_units[k, u] + sum{h in House} lca_house_units[k, h];

subject to complicating_cst_lca{k in Lca_kpi, l in ResourceBalances, p in Period, t in Time[p]}:
Network_supply_lca[k,l,p,t] - Network_demand_lca[k,l,p,t] = ( sum{f in FeasibleSolutions, h in House}(lambda[f,h] *(Grid_supply[l,f,h,p,t]-Grid_demand[l,f,h,p,t])) +sum {r in Units} Units_demand[l,r,p,t]-sum {b in Units} Units_supply[l,b,p,t])* dp[p] * dt[p];

subject to LU_op_cst{k in Lca_kpi, l in ResourceBalances}:
lca_op[k, l] = sum{p in PeriodStandard,t in Time[p]}(lca_kpi_supply[k,l,p,t]*Network_supply_lca[k,l,p,t] - lca_kpi_demand[k,l,p,t]*Network_demand_lca[k,l,p,t]);

subject to LU_tot_cst{k in Lca_kpi}:
lca_tot[k] = lca_inv[k] + sum{l in ResourceBalances} lca_op[k, l];

subject to LU_tot_house_cst{k in Lca_kpi, h in House}:
lca_tot_house[k, h] = lca_house_units[k, h] + sum{f in FeasibleSolutions,l in ResourceBalances,p in PeriodStandard,t in Time[p]} (lca_kpi_supply[k,l,p,t]*Grid_supply[l,f,h,p,t]-lca_kpi_demand[k,l,p,t]*Grid_demand[l,f,h,p,t])*lambda[f,h]*dp[p]*dt[p];



######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#--objectives
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# parameters and variables for epsilon constraints
param EMOO_CAPEX default 1000;
param EMOO_OPEX default 1000;
param EMOO_GWP default 1000;
param EMOO_TOTEX default 1000;
param EMOO_grid default 0;
param EMOO_lca{k in Lca_kpi} default 1e6;

var EMOO_slack                >= 0, <= abs(EMOO_CAPEX) * Area_tot;
var EMOO_slack_opex           >= 0, <= abs(EMOO_OPEX)*Area_tot;
var EMOO_slack_gwp            >= 0, <= abs(EMOO_GWP)*Area_tot;
var EMOO_slack_totex          >= 0, <= abs(EMOO_TOTEX)*Area_tot;


#--------------------------------------------------------------------------------------------------------------------#
#---Transformer capacity constraints
#--------------------------------------------------------------------------------------------------------------------#

subject to TransformerCapacity_supply{l in ResourceBalances,p in PeriodStandard,t in Time[p]}:
Network_supply[l,p,t] <= TransformerCapacity[l] * dp[p] * dt[p];

subject to TransformerCapacity_demand{l in ResourceBalances,p in PeriodStandard,t in Time[p]}:
Network_demand[l,p,t] <= TransformerCapacity[l] * dp[p] * dt[p];

subject to EMOO_grid_constraint {l in ResourceBalances, p in Period, t in Time[p]: l =  'Electricity'}:
Network_supply[l,p,t]-Network_demand[l,p,t] <= if EMOO_grid!=0 then EMOO_grid*sum{ts in Time[p]}((Network_supply[l,p,ts]-Network_demand[l,p,ts])*dt[p]/card(Time[p])) else 1e9;

subject to disallow_exchanges_1{l in ResourceBalances, p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
sum{f in FeasibleSolutions, h in House} (Grid_supply[l,f,h,p,t] * lambda[f,h]*dp[p]*dt[p]) = Network_supply[l,p,t];

subject to disallow_exchanges_2{l in ResourceBalances, p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
sum{f in FeasibleSolutions, h in House} (Grid_demand[l,f,h,p,t] * lambda[f,h]*dp[p]*dt[p]) = Network_demand[l,p,t];

#subject to EMOO_c2 {l in ResourceBalances, p in Period, t in Time[p]: l =  'Electricity'}:
#Network_supply[l,p,t] <=  if EMOO_grid!=0 then EMOO_grid*sum{tau in Time[p]}(Network_supply[l,p,tau]*dt[p]/card(Time[p])) else 1e9;

#subject to EMOO_c3 {l in ResourceBalances, p in Period, t in Time[p]: l =  'Electricity'}:
#Network_demand[l,p,t] <= if EMOO_grid!=0 then EMOO_grid*sum{tau in Time[p]}(Network_demand[l,p,tau]*dt[p]/card(Time[p])) else 1e9;



# Multi objective optimization
subject to EMOO_CAPEX_constraint: # beta_cap
Costs_inv + EMOO_slack = EMOO_CAPEX * Area_tot;

subject to EMOO_OPEX_constraint: # beta_op
Costs_op + EMOO_slack_opex = EMOO_OPEX * Area_tot;

subject to EMOO_GWP_constraint: # beta_gwp
GWP_tot + EMOO_slack_gwp = EMOO_GWP * Area_tot;

subject to EMOO_TOTEX_constraint: # beta_tot
Costs_tot + EMOO_slack_totex = EMOO_TOTEX * Area_tot;

subject to EMOO_lca_constraint{k in Lca_kpi} :
lca_tot[k] <= EMOO_lca[k] * Area_tot;


param penalty_ratio default 1e-6;
var penalties default 0;

subject to penalties_contraints:
penalties = penalty_ratio * (Costs_inv + Costs_op + sum{k in Lca_kpi} lca_tot[k] +
            sum{l in ResourceBalances,p in PeriodExtrem,t in Time[p]} (Network_supply[l,p,t] + Network_demand[l,p,t])) + Costs_cft;


# objective functions
minimize TOTEX:
Costs_tot + penalties;

minimize OPEX:
Costs_op + penalties;

minimize CAPEX: # the second term is added to correspond to objective set in design_cst
Costs_inv + penalties;

minimize GWP:
GWP_tot + penalties;

minimize Human_toxicity:
lca_tot["Human_toxicity"] + penalties;

minimize land_use:
lca_tot["land_use"] + penalties;