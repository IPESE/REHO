######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---OVERARCHING MOBILITY MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model
# Declare generic parameters and constraints valid for the transport sector

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).


# ----------------------------------------- PARAMETERS ---------------------------------------
param Population default 10; # will multiply the domestic demand ? 
param DailyDist default 36.8; # [1]
param max_travel_time default 3; # 1.3 hours mean

set transport_Units; # TODO : check if dynamic to the rest of the code
set Activities := {"work","leisure","travel"}; 
set Districts default {};
param Mode_Speed{u in transport_Units} default 37.1; # [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
param Daily_Profile{u in transport_Units,p in Period,t in Time[p]} default 1; # initialized through the function generate_mobility_parameters

param max_share_cars default 0.7;
param min_share_cars default 0;

param max_share_MD default 1;
param min_share_MD default 0;

# ----------------------------------------- VARIABLES ---------------------------------------
var travel_time{p in Period,t in Time[p]} >= 0 ; #pkm

#-VARIABLES (for public transport)
var pkm_PT_train{p in Period,t in Time[p]} >= 0 ;
var pkm_PT_bus{p in Period,t in Time[p]} >= 0 ;

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to travel_time_c1{p in Period,t in Time[p]}:
# travel_time[p,t] = sum{u in transport_Units : u != "Public_transport"}(Units_supply['Mobility',u,p,t] / Mode_Speed[u]) +( Network_supply['Mobility',p,t] / dp[p] / Mode_Speed['Public_transport']);
travel_time[p,t] = sum{u in transport_Units : substr(u, 1, 2) != "PT"}(Units_supply['Mobility',u,p,t] / Mode_Speed[u]) +( pkm_PT_bus[p,t] / dp[p]/ Mode_Speed['PT_bus'] + pkm_PT_train[p,t]/ dp[p] / Mode_Speed['PT_train']);




subject to travel_time_c2{p in Period}:
sum {t in Time[p]}(travel_time[p,t]) <= max_travel_time * Population; 


# constraint on the max share of cars

subject to allcars_maxshare{p in PeriodStandard}:
sum {u in UnitsOfType['ICE'], t in Time[p]} (Units_supply['Mobility',u,p,t]) + sum {u in UnitsOfType['EV'], t in Time[p]} (Units_supply['Mobility',u,p,t]) <= max_share_cars * Population * DailyDist;

subject to allcars_minshare{p in PeriodStandard}:
sum {u in UnitsOfType['ICE'], t in Time[p]} (Units_supply['Mobility',u,p,t]) + sum {u in UnitsOfType['EV'], t in Time[p]} (Units_supply['Mobility',u,p,t]) >= min_share_cars * Population * DailyDist;

subject to MD_maxshare{p in PeriodStandard}:
sum {u in UnitsOfType['Bike'], t in Time[p]} (Units_supply['Mobility',u,p,t]) + sum {u in UnitsOfType['EBike'], t in Time[p]} (Units_supply['Mobility',u,p,t]) <= max_share_MD * Population * DailyDist;

subject to MD_minshare{p in PeriodStandard}:
sum {u in UnitsOfType['Bike'], t in Time[p]} (Units_supply['Mobility',u,p,t]) + sum {u in UnitsOfType['EBike'], t in Time[p]} (Units_supply['Mobility',u,p,t]) >= min_share_MD * Population * DailyDist;



#--------------------------------------------------------------------------------------------------------------------#
#-PUBLIC TRANSPORTS
#--------------------------------------------------------------------------------------------------------------------#
# contraindre Network_supply avec un profil de capacité horaire
#-PARAMETERS
# param transport_public_capacity{p in Period, t in Time[p]} default 150; # pkm : availability of public transport each hour in pkm
param max_share_PT default 0.24; # [1] G 3.3.1.6 : share of trains amounts to ~ 20%
param max_share_PT_train default  0.2; # source : OFS says 20 %
param max_share_PT_bus default 0.05;

param min_share_PT default 0; # [1] G 3.3.1.6 : share of trains amounts to ~ 20%
param min_share_PT_train default 0;
param min_share_PT_bus default 0;


#-CONSTRAINTS

# subject to TP_c1{p in Period, t in Time[p]}:
# Network_supply["Mobility",p,t] /d[p] <= transport_public_capacity[p,t];

subject to TP_c2{p in Period, t in Time[p]}:
Network_supply["Mobility",p,t]  = pkm_PT_train[p,t] + pkm_PT_bus[p,t];

subject to TP_c3{p in Period, t in Time[p]}:
Network_demand["Mobility",p,t]  = 0;

subject to TP_train_maxshare{p in PeriodStandard}:
sum {t in Time[p]}(pkm_PT_train[p,t])/dp[p] <= max_share_PT_train * Population * DailyDist;

subject to TP_bus_maxshare{p in PeriodStandard}:
sum {t in Time[p]}(pkm_PT_bus[p,t])/dp[p] <= max_share_PT_bus * Population * DailyDist;

subject to TP_maxshare{p in PeriodStandard}:
sum {t in Time[p]}(Network_supply["Mobility",p,t])/dp[p] <= max_share_PT * Population * DailyDist; 



subject to TP_train_minshare{p in PeriodStandard}:
sum {t in Time[p]}(pkm_PT_train[p,t])/dp[p] >= min_share_PT_train * Population * DailyDist;

subject to TP_bus_minshare{p in PeriodStandard}:
sum {t in Time[p]}(pkm_PT_bus[p,t])/dp[p] >= min_share_PT_bus * Population * DailyDist;

subject to TP_minshare{p in PeriodStandard}:
sum {t in Time[p]}(Network_supply["Mobility",p,t])/dp[p] >= min_share_PT * Population * DailyDist; 


