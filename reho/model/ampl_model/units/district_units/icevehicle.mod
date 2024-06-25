######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---INTERNAL COMBUSTION ENGINE VEHICLE MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).
# [2] Rios-Torres, J., Liu, J., & Khattak, A. (2019). Fuel consumption for various driving styles in conventional and hybrid electric vehicles: Integrating driving cycle predictions with fuel consumption optimization*. International Journal of Sustainable Transportation, 13(2), 123–137. https://doi.org/10.1080/15568318.2018.1445321



# ----------------------------------------- PARAMETERS ---------------------------------------
# Usage
param n_ICEperhab default 1; # [1] G 2.1.2.1 on average 0.49 vehicles per dwelling (to be multiplied with persons/dwelling )
param max_n_ICE := n_ICEperhab * Population;
param ff_ICE default 1.56; # [1]
param max_share_ICE default 0.70; # [4] G 3.3.1.6 : share of cars is 66 %
param min_share_ICE default 0.0; 
param max_daily_time_spend_travellingICE{u in UnitsOfType['ICE']} default 0.9;

# Technical characteristics
param ICE_eff{u in UnitsOfType['ICE']} default 2.12;  # km/kWh [2] : 4.99 L/100 km and 34 MJ/L on average for diesel/gasoline => 2.12 km/kWh
# param ICE_capacity{u in UnitsOfType['ICE']} default 377; # average capacity of a tank : 40 L => 377 kWh (I removed the tank modelling)
param max_speed_ICE default 60; # pkm per hour (needed or not ?)

# ----------------------------------------- VARIABLES ---------------------------------------
var n_ICE{u in UnitsOfType['ICE']} integer >= 0;
var share_ICE{u in UnitsOfType['ICE'],p in Period} >= 0;
# var ICE_E_tank{u in UnitsOfType['ICE'],p in Period,t in Time[p]} >= 0; # storage
# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to ICE_EB_c1{u in UnitsOfType['ICE'],p in Period,t in Time[p]}:
Units_demand['FossilFuel',u,p,t ]= Units_supply['Mobility',u,p,t] /  ICE_eff[u]/ ff_ICE;

subject to ICE_EB_c2{u in UnitsOfType['ICE'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] = share_ICE[u,p] * Daily_Profile[u,p,t];

subject to ICE_c1{u in UnitsOfType['ICE'],p in PeriodStandard,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= Mode_Speed[u] * n_ICE[u] * EV_activity['travel',"EV_district",p,t]; # TODO : code an ICE activity profile, and/or rename the variable CAR_activity 

subject to ICE_c2{u in UnitsOfType["ICE"]}:
n_ICE[u] = Units_Mult[u];


# Boundaries
subject to ICE_cb1{u in UnitsOfType["ICE"]}:
n_ICE[u] <= max_n_ICE;

# subject to ICE_cb2{u in UnitsOfType['ICE'],p in Period,t in Time[p]}:
# ICE_E_tank[u,p,t] <= ICE_capacity[u] * n_ICE[u];

subject to ICE_maxshare{p in PeriodStandard}:
sum {u in UnitsOfType['ICE'], t in Time[p]} (Units_supply['Mobility',u,p,t]) <= max_share_ICE * Population * DailyDist;

subject to ICE_minshare{p in PeriodStandard}:
sum {u in UnitsOfType['ICE'], t in Time[p]} (Units_supply['Mobility',u,p,t]) >= min_share_ICE * Population * DailyDist;


subject to ICE_timeoftravel{p in Period,u in UnitsOfType['ICE']}:
sum {t in Time[p]}(Units_supply['Mobility',u,p,t])/ff_ICE /Mode_Speed[u]  <= max_daily_time_spend_travellingICE[u] * n_ICE[u] ; 