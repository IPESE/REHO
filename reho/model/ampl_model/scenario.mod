######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# OBJECTIVE FUNCTIONS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param penalty_ratio default 1e-6;
var penalties default 0;

subject to penalties_contraints:
penalties = sum{h in House} Costs_House_cft[h] +
            penalty_ratio * Costs_grid_connection +
            penalty_ratio * (Costs_op + tau*(Costs_inv + Costs_rep)) +
            penalty_ratio * (GWP_op + GWP_constr) +
            penalty_ratio * sum{l in ResourceBalances,h in HousesOfLayer[l],p in Period,t in Time[p]} (Grid_supply[l,h,p,t] + Grid_demand[l,h,p,t]) +
            penalty_ratio * sum{l in ResourceBalances,p in Period,t in Time[p]} (Network_supply[l,p,t] + Network_demand[l,p,t]);

minimize OPEX: 
Costs_op + Costs_grid_connection + penalties;

minimize CAPEX: 
tau*(Costs_inv + Costs_rep) + penalties;

minimize TOTEX:
tau*(Costs_inv + Costs_rep) + Costs_op + Costs_grid_connection + penalties;

minimize GWP:
GWP_op + GWP_constr + penalties;

minimize MAX_EXPORT:
-sum{p in PeriodStandard,t in Time[p]} ( Network_demand['Electricity',p,t] - Network_supply['Electricity',p,t] ) * dp[p] * dt[p] / 1000 + penalties;

#--------------------------------------------------------------------------------------------------------------------#
# Actors
#--------------------------------------------------------------------------------------------------------------------#
set Obj_fct := {'TOTEX', 'OPEX', 'CAPEX', 'GWP', "Owners", "Renters", "Utility"};
param beta_duals{o in Obj_fct} default 0;

param nu_Renters{h in House} default beta_duals["Renters"];
param nu_Owners{h in House}  default beta_duals["Owners"];
param nu_Utility default beta_duals["Utility"];

param C_rent_fix{h in House} default 0;
param Cost_self_consumption{h in House} default Cost_supply_cst['Electricity'];
param Cost_supply_district{h in House, l in ResourceBalances} default Cost_supply_cst[l];
param Cost_demand_district{h in House, l in ResourceBalances} default Cost_demand_cst[l];

param renter_subsidies{h in House} default 0;
param owner_subsidies{h in House} default 0;

var cost_actors;
var objective_owners{h in House};
var objective_renters{h in House};
var objective_utility;

subject to obj_renters{h in House}:
objective_owners[h] = C_rent_fix[h] 
                    + sum{p in Period, t in Time[p], u in UnitsOfType['PV'] inter UnitsOfHouse[h]} ((Units_supply['Electricity',u,p,t] - Grid_demand['Electricity',h,p,t]) * Cost_self_consumption[h])  
                    + sum{l in ResourceBalances, p in Period, t in Time[p]} (Cost_demand_district[h,l] * Grid_demand[l,h,p,t])  
                    - Costs_House_inv[h] * tau
                    - Costs_House_yearly[h]
                    + owner_subsidies[h];

subject to obj_owners{h in House}:
objective_renters[h] = C_rent_fix[h]
                    + sum{l in ResourceBalances, p in Period, t in Time[p]} (Cost_supply_district[h,l] * Grid_supply[l,h,p,t]) 
                    + sum{p in Period, t in Time[p], u in UnitsOfType['PV'] inter UnitsOfHouse[h]} ((Units_supply['Electricity',u,p,t] - Grid_demand['Electricity',h,p,t]) * Cost_self_consumption[h])
                    - renter_subsidies[h];

subject to obj_utility:
objective_utility = sum{h in House, l in ResourceBalances, p in Period, t in Time[p]} (Cost_supply_district[h,l] * Grid_supply[l,h,p,t])
                    - sum{h in House, l in ResourceBalances, p in Period, t in Time[p]} (Cost_demand_district[h,l] * Grid_demand[l,h,p,t]);

subject to actors_costs_SP:
cost_actors = sum{h in House} (nu_Renters[h] * objective_renters[h]) + sum{h in House} (nu_Owners[h] * objective_owners[h]) + nu_Utility * objective_utility;

#--------------------------------------------------------------------------------------------------------------------#
# Decomposition
#--------------------------------------------------------------------------------------------------------------------#

minimize SP_obj_fct:
beta_duals['OPEX'] * (Costs_op + Costs_grid_connection) + beta_duals['CAPEX'] * tau * (Costs_inv + Costs_rep) + beta_duals['GWP'] * (GWP_op  + GWP_constr) +
penalties + cost_actors;

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# EPSILON CONSTRAINTS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param EMOO_CAPEX default 0;
param EMOO_OPEX default 0;
param EMOO_TOTEX default 0;
param EMOO_GWP default 0;

param EMOO_grid default 0;
param EMOO_network default 0;
param EMOO_GU_demand default 1e9;
param EMOO_GU_supply default 1e9;
param E_house_max{h in House} =  max{p in PeriodStandard,t in Time[p]} Domestic_electricity[h,p,t];

var EMOO_slack_capex 						>= 0, <= abs(EMOO_CAPEX)*(sum{h in House} ERA[h]);
var EMOO_slack_opex							>= 0, <= abs(EMOO_OPEX)*(sum{h in House} ERA[h]);
var EMOO_slack_totex						>= 0, <= abs(EMOO_TOTEX)*(sum{h in House} ERA[h]);
var EMOO_slack_gwp							>= 0, <= abs(EMOO_GWP)*(sum{h in House} ERA[h]);

subject to EMOO_CAPEX_constraint:
tau*(Costs_inv +Costs_rep )+ EMOO_slack_capex = EMOO_CAPEX*(sum{h in House} ERA[h]);

subject to EMOO_OPEX_constraint:
Costs_op + EMOO_slack_opex = EMOO_OPEX*(sum{h in House} ERA[h]);

subject to EMOO_TOTEX_constraint:
Costs_op + tau*(Costs_inv +Costs_rep ) + EMOO_slack_totex = EMOO_TOTEX*(sum{h in House} ERA[h]);

subject to EMOO_GWP_constraint:
GWP_op + GWP_constr + EMOO_slack_gwp = EMOO_GWP*(sum{h in House} ERA[h]);


subject to EMOO_grid_constraint{l in ResourceBalances,hl in HousesOfLayer[l],p in PeriodStandard,t in Time[p]: l = 'Electricity' }:
Grid_supply[l,hl,p,t] - Grid_demand[l,hl,p,t]  <= if EMOO_grid!=0 then EMOO_grid*sum{i in Time[p]}((Grid_supply[l,hl,p,i] - Grid_demand[l,hl,p,i] )*dt[p])/(card(Time[p])) else 1e8;

subject to EMOO_network_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l = 'Electricity' }:
Network_supply[l,p,t] - Network_demand[l,p,t] <= if EMOO_network!=0 then EMOO_network*sum{i in Time[p]}((Network_supply[l,p,i] - Network_demand[l,p,i])*dt[p])/(card(Time[p])) else 1e8;

subject to EMOO_GU_demand_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
Network_demand[l,p,t] <=  sum{h in House} (E_house_max[h]* EMOO_GU_demand);

subject to EMOO_GU_supply_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
Network_supply[l,p,t] <=  sum{h in House} (E_house_max[h]* EMOO_GU_supply );


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# PROFILES
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

subject to network_total_supply{l in ResourceBalances,p in Period,t in Time[p]}:
Network_supply[l,p,t] <= sum{h in House}(Grid_supply[l,h,p,t]);

subject to network_total_demand{l in ResourceBalances,p in Period,t in Time[p]}:
Network_demand[l,p,t] <= sum{h in House}(Grid_demand[l,h,p,t]);

#--------------------------------------------------------------------------------------------------------------------#
# Annual profiles
#--------------------------------------------------------------------------------------------------------------------#
var AnnualUnit_Q{s in Services,u in UnitsOfService[s]}          >= 0;   #MWh
var AnnualUnit_in{l in ResourceBalances,u in UnitsOfLayer[l]}   >= 0;   #MWh
var AnnualUnit_out{l in ResourceBalances,u in UnitsOfLayer[l]}  >= 0;   #MWh
var AnnualHouse_Q{s in Services,h in House}                     >= 0;   #MWh
var AnnualDomestic_electricity{h in House}                      >= 0;   #MWh
var AnnualNetwork_supply{l in ResourceBalances}                 >= 0;   #MWh
var AnnualNetwork_demand{l in ResourceBalances}                 >= 0;   #MWh
var AnnualHeatGainHouse{h in House}                             >= 0;   #MWh
var AnnualSolarGainHouse{h in House}                            >= 0;   #MWh

param EMOO_elec_export default 0;
var EMOO_slack_elec_export 						>= 0;

subject to EMOO_elec_export_constraint:
    sum{l in ResourceBalances,p in PeriodStandard,t in Time[p]} ( Network_demand[l,p,t] - Network_supply[l,p,t] ) * dp[p] * dt[p] / 1000  =  EMOO_slack_elec_export + EMOO_elec_export * (sum{h in House} ERA[h]);

subject to total_units_Q{s in Services, u in UnitsOfService[s]}:
AnnualUnit_Q[s,u] = sum{st in StreamsOfService[s] inter StreamsOfUnit[u],p in PeriodStandard,t in Time[p]}(Streams_Q[s,st,p,t]*dp[p]*dt[p]/1000);

subject to total_houses_Q{s in Services,h in House}:
AnnualHouse_Q[s,h] = sum{st in StreamsOfService[s] inter StreamsOfBuilding[h],p in PeriodStandard,t in Time[p]}(Streams_Q[s,st,p,t]*dp[p]*dt[p]/1000);

# this constraint is not working for centralized with several buildings
#subject to total_houses_Q{s in Services, h in House, u_dhw in UnitsOfType['WaterTankDHW'], u_sh in UnitsOfType['WaterTankSH']}:
#AnnualHouse_Q[s,h] = sum{st in StreamsOfService[s] diff StreamsOfBuilding[h] diff StreamsOfUnit[u_dhw] diff StreamsOfUnit[u_sh], p in PeriodStandard,t in Time[p]}(Streams_Q[s,st,p,t]*dp[p]*dt[p]/1000);

subject to total_unit_in{l in ResourceBalances,u in UnitsOfLayer[l]}:
AnnualUnit_in[l,u] = sum{p in PeriodStandard,t in Time[p]}(Units_demand[l,u,p,t]*dp[p]*dt[p]/1000);

subject to total_unit_out{l in ResourceBalances,u in UnitsOfLayer[l]}:
AnnualUnit_out[l,u] = sum{p in PeriodStandard,t in Time[p]}(Units_supply[l,u,p,t]*dp[p]*dt[p]/1000);

subject to total_domestic_electricity{h in House}:
AnnualDomestic_electricity[h] = sum{p in PeriodStandard,t in Time[p]}(Domestic_electricity[h,p,t]*dp[p]*dt[p]/1000);

subject to total_network_supply{l in ResourceBalances}:
 AnnualNetwork_supply[l] = sum{p in PeriodStandard,t in Time[p]} (Network_supply[l,p,t]*dp[p]*dt[p]/1000);

subject to total_network_demand{l in ResourceBalances}:
 AnnualNetwork_demand[l] = sum{p in PeriodStandard,t in Time[p]} (Network_demand[l,p,t]*dp[p]*dt[p]/1000);

subject to total_heat_gains{h in House}:
AnnualHeatGainHouse[h] = sum{p in PeriodStandard,t in Time[p]}(HeatGains[h,p,t]*dp[p]*dt[p]/1000);

subject to total_solar_gains{h in House}:
AnnualSolarGainHouse[h] = sum{p in PeriodStandard,t in Time[p]}(SolarGains[h,p,t]*dp[p]*dt[p]/1000);

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# SPECIFIC CONSTRAINTS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

### Force hydrogen export

param HydrogenAnnualExport >= 0 default 0;  # set as a parameter for an annual H2 export [kWh]

subject to forced_H2_annual_export:
HydrogenAnnualExport = sum{p in PeriodStandard,t in Time[p]} Network_demand['Hydrogen',p,t]*dp[p]*dt[p];

var HydrogenDailyExport >= 0;  # set as a variable for an optimal daily H2 export [kWh]

subject to forced_H2_fixed_daily_export{p in PeriodStandard}:
HydrogenDailyExport = sum{t in Time[p]} Network_demand['Hydrogen',p,t]*dt[p];
