######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---OBJECTIVE FUNCTIONS
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
 
minimize land_use:
lca_tot["land_use"]  + penalties;

minimize mine_res:
lca_tot["mine_res"] + penalties;
 
minimize Human_toxicity:
lca_tot["Human_toxicity"] + penalties;

#--------------------------------------------------------------------------------------------------------------------#
#---Decomposition
#--------------------------------------------------------------------------------------------------------------------#

set Obj_fct := Lca_kpi union {'TOTEX', 'OPEX', 'CAPEX', 'GWP'};
param beta_duals{o in Obj_fct} default 0;

minimize SP_obj_fct:
beta_duals['OPEX'] * (Costs_op + Costs_grid_connection) + beta_duals['CAPEX'] * tau*(Costs_inv + Costs_rep) + beta_duals['GWP'] * (GWP_op  + GWP_constr) +
sum{o in Obj_fct inter Lca_kpi} beta_duals[o] * lca_tot[o] + penalties;


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---EPSILON CONSTRAINTS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param EMOO_CAPEX default 0;
param EMOO_OPEX default 0;
param EMOO_TOTEX default 0;
param EMOO_GWP default 0;
param EMOO_lca{k in Lca_kpi} default 1e6;

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

subject to EMOO_lca_constraint{k in Lca_kpi} :
lca_tot[k] <= EMOO_lca[k]*(sum{h in House} ERA[h]);


subject to EMOO_grid_constraint{l in ResourceBalances,hl in HousesOfLayer[l],p in PeriodStandard,t in Time[p]: l = 'Electricity' }:
Grid_supply[l,hl,p,t] - Grid_demand[l,hl,p,t]  <= if EMOO_grid!=0 then EMOO_grid*sum{i in Time[p]}((Grid_supply[l,hl,p,i] - Grid_demand[l,hl,p,i] )*dt[p])/(card(Time[p])) else 1e8;

subject to EMOO_network_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l = 'Electricity' }:
Network_supply[l,p,t] - Network_demand[l,p,t] <= if EMOO_network!=0 then EMOO_network*sum{i in Time[p]}((Network_supply[l,p,i] - Network_demand[l,p,i])*dt[p])/(card(Time[p])) else 1e8;

subject to EMOO_GU_demand_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
Network_demand[l,p,t] <= TransformerCapacityAdd[l] + sum{h in House} (E_house_max[h]* EMOO_GU_demand);

subject to EMOO_GU_supply_constraint{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l =  'Electricity'}:
Network_supply[l,p,t] <= TransformerCapacityAdd[l] + sum{h in House} (E_house_max[h]* EMOO_GU_supply );


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---PROFILES
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

subject to network_total_supply{l in ResourceBalances,p in Period,t in Time[p]}:
Network_supply[l,p,t] <= sum{h in House}(Grid_supply[l,h,p,t]);

subject to network_total_demand{l in ResourceBalances,p in Period,t in Time[p]}:
Network_demand[l,p,t] <= sum{h in House}(Grid_demand[l,h,p,t]);

#--------------------------------------------------------------------------------------------------------------------#
#---Annual profiles
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

subject to EMOO_elec_export_constraint{l in ResourceBalances: l = 'Electricity'}:
    sum{p in PeriodStandard,t in Time[p]} ( Network_demand[l,p,t] - Network_supply[l,p,t] ) * dp[p] * dt[p] / 1000  =  EMOO_slack_elec_export + EMOO_elec_export * (sum{h in House} ERA[h]);

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


