######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---OVERARCHING MOBILITY MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model
# Declare generic parameters and constraints valid for the transport sector

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).


# ----------------------------------------- PARAMETERS ---------------------------------------
param Population default 10; # will multiply the domestic demand. Caution : unlinked default value duplicata in generate_mobility_parameters

set transport_Units; # TODO : check if dynamic to the rest of the code
set transport_Units_MD;
set transport_Units_cars;
set transport_Units_PT :={'PT_train','PT_bus'};
set Activities := {"work","leisure","travel"}; 
set Districts default {};
param Mode_Speed{u in transport_Units} default 37.1; # km/h - [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
param Daily_Profile{u in transport_Units,p in Period,t in Time[p]} default 1; # [-] initialized through the function generate_mobility_parameters
param Domestic_energy_pkm{dist in Distances ,p in Period ,t in Time[p]} >= 0; # pkm

param max_share{u in transport_Units, dist in Distances} default 1; # [-]
param min_share{u in transport_Units, dist in Distances} default 0; # [-]

set Modes := {"cars","MD","PT"};
param max_share_modes{m in Modes, dist in Distances} default 1; # [-] - [1] G 3.3.1.6 
param min_share_modes{m in Modes, dist in Distances} default 0; # [-] - 

# ----------------------------------------- VARIABLES ---------------------------------------
var pkm_supply{u in transport_Units,dist in Distances ,p in Period ,t in Time[p]} >= 0; # pkm
var pkm_PT_train{p in Period,t in Time[p]} >= 0 ; # pkm
var pkm_PT_bus{p in Period,t in Time[p]} >= 0 ; # pkm

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to pkm_distancetypes_c2_1{u in transport_Units_MD union transport_Units_cars,p in PeriodStandard,t in Time[p]}:
 sum{dist in Distances} (pkm_supply[u,dist,p,t]) = Units_supply['Mobility',u,p,t] ;

subject to pkm_distancetypes_c2_bus{p in PeriodStandard,t in Time[p]}:
sum{dist in Distances} ( pkm_supply["PT_bus",dist,p,t]) = pkm_PT_bus[p,t] /dp[p] ;

subject to pkm_distancetypes_c2_train{p in PeriodStandard,t in Time[p]}:
 sum{dist in Distances} ( pkm_supply["PT_train",dist,p,t]) = pkm_PT_train[p,t] /dp[p]  ;

subject to pkm_distancetypes_c3{dist in Distances,p in PeriodStandard,t in Time[p]}:
Domestic_energy_pkm[dist,p,t] = sum{u in transport_Units } (pkm_supply[u,dist,p,t]);


# constraint on the max share of cars
subject to allcars_maxshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_cars, t in Time[p]}(pkm_supply[u,dist,p,t]) <= Population *  (DailyDist[dist]*max_share_modes['cars',dist] );

subject to allcars_minshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_cars, t in Time[p]}(pkm_supply[u,dist,p,t])  >=  Population *  (DailyDist[dist] *min_share_modes['cars',dist]);

subject to MD_maxshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_MD, t in Time[p]}(pkm_supply[u,dist,p,t]) <= Population *  (DailyDist[dist] * max_share_modes['MD',dist] );

subject to MD_minshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_MD, t in Time[p]}(pkm_supply[u,dist,p,t]) >= Population *  (DailyDist[dist] * min_share_modes['MD',dist] );


#--------------------------------------------------------------------------------------------------------------------#
#-PUBLIC TRANSPORTS
#--------------------------------------------------------------------------------------------------------------------#
#-PARAMETERS
param max_share_PT default 0.24; # [1] G 3.3.1.6 : share of trains amounts to ~ 20%
param min_share_PT default 0; # [1] G 3.3.1.6 : share of trains amounts to ~ 20%


#-CONSTRAINTS

subject to TP_c2{p in Period, t in Time[p]}:
Network_supply["Mobility",p,t]  = pkm_PT_train[p,t] + pkm_PT_bus[p,t];

subject to TP_c3{p in Period, t in Time[p]}:
Network_demand["Mobility",p,t]  = 0;

subject to TP_train_maxshare{p in PeriodStandard,dist in Distances}:
sum {t in Time[p]}(pkm_supply["PT_train",dist,p,t])<= max_share["PT_train",dist]* Population * DailyDist[dist];

subject to TP_bus_maxshare{p in PeriodStandard,dist in Distances}:
sum {t in Time[p]}(pkm_supply["PT_bus",dist,p,t])<= max_share["PT_bus",dist] * Population * DailyDist[dist];

subject to TP_maxshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_PT, t in Time[p]}(pkm_supply[u,dist,p,t])  <= Population * (DailyDist[dist] * max_share_modes['PT',dist] ); 



subject to TP_train_minshare{p in PeriodStandard,dist in Distances}:
sum {t in Time[p]}(pkm_PT_train[p,t])/dp[p] >= min_share["PT_train",dist] * Population * DailyDist[dist];

subject to TP_bus_minshare{p in PeriodStandard,dist in Distances}:
sum {t in Time[p]}(pkm_PT_bus[p,t])/dp[p] >= min_share["PT_bus",dist] * Population * DailyDist[dist];

subject to TP_minshare{p in PeriodStandard,dist in Distances}:
sum {u in transport_Units_PT, t in Time[p]}(pkm_supply[u,dist,p,t])  >= Population * (DailyDist[dist] * min_share_modes['PT',dist] ); 


