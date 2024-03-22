######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---INTERNAL COMBUSTION VEHICLE MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).


# ----------------------------------------- PARAMETERS ---------------------------------------
# Usage
param n_ICEperhab default 0.9;
param max_n_ICE := n_ICEperhab * Population;
param ff_ICE default 1.56;

# Technical characteristics
param ICE_eff{u in UnitsOfType['ICE']} default 18;  # km/kWhTODO : find a source (EV  : 6 kWh/km * 3)
param ICE_capacity{u in UnitsOfType['ICE']} default 70; #TODO source
param max_speed_ICE default 60; # pkm per hour [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015

# ----------------------------------------- VARIABLES ---------------------------------------
var n_ICE{u in UnitsOfType['ICE']} integer >= 0;
var share_ICE{u in UnitsOfType['ICE']} >= 0;
var ICE_E_tank{u in UnitsOfType['ICE'],p in Period,t in Time[p]} >= 0; # storage
# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to ICE_EB_c1{u in UnitsOfType['ICE'],p in Period,t in Time[p]}:
ICE_E_tank[u,p,t] = Units_demand['FossilFuel',u,p,t] - Units_supply['Mobility',u,p,t] /  ICE_eff[u]/ ff_ICE;

subject to ICE_EB_c2{u in UnitsOfType['ICE'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] = share_ICE[u] * Domestic_energy['Mobility',p,t];

subject to ICE_c1{u in UnitsOfType['ICE'],p in Period,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= max_speed_ICE * n_ICE[u];

subject to ICE_c2{u in UnitsOfType["ICE"]}:
n_ICE[u] = Units_Mult[u];


# Boundaries
subject to ICE_cb1{u in UnitsOfType["ICE"]}:
n_ICE[u] <= max_n_ICE;

subject to ICE_cb2{u in UnitsOfType['ICE'],p in Period,t in Time[p]}:
ICE_E_tank[u,p,t] <= ICE_capacity[u] * n_ICE[u];



