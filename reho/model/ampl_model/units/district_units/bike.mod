######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---BIKE MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).


# ----------------------------------------- PARAMETERS ---------------------------------------
# param max_speed default 13.3; # pkm per hour [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
param max_distperday default 10; # pkm (per bike) - moyenne mobilité douce : 2.8km per day [1] T 3.3.1.1
param n_bikesperhab default 1; # number
param max_n_bikes := n_bikesperhab * Population;

# [1] G 3.3.1.6 : share of bikes and walking amounts to ~ 8%

# param max_modal_share default 1; # 8 % de mobilité douce - [1] Fig G 3.3.1.1 : Choix du moyen de transport, en 2015
param tau_relaxation default 0.03; # [-] relaxation of the daily profile constraint by 3%. 

# ----------------------------------------- VARIABLES ---------------------------------------
var n_bikes{u in UnitsOfType['Bike']} integer >= 0; # number
var share_bike{u in UnitsOfType['Bike'],p in Period } >= 0; # %
# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to Bikes_c1{u in UnitsOfType['Bike'],p in Period,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= Mode_Speed[u] * n_bikes[u];

#subject to Bikes_c2{u in UnitsOfType['Bike'],p in Period}:
#sum {i in Time[p]}(Units_supply['Mobility',u,p,i]) <= max_distperday * n_bikes[u] ;

#subject to Bikes_cb1:
#sum{u in UnitsOfType["Bike"]}(n_bikes[u]) <= max_n_bikes;

subject to Bikes_cb2{u in UnitsOfType["Bike"]}:
n_bikes[u] = Units_Mult[u];

subject to Bikes_profile1{u in UnitsOfType['Bike'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] <= share_bike[u,p] * Daily_Profile[u,p,t] * (1+ tau_relaxation);

subject to Bikes_profile2{u in UnitsOfType['Bike'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] >= share_bike[u,p] * Daily_Profile[u,p,t] * (1 - tau_relaxation);

subject to Bikes_maxshare{u in UnitsOfType['Bike'],p in PeriodStandard, dist in Distances}:
sum {t in Time[p]} (pkm_supply[u,dist,p,t]) <= max_share[u,dist] * Population * DailyDist[dist];

subject to Bikes_minshare{u in UnitsOfType['Bike'],p in PeriodStandard, dist in Distances}:
sum {t in Time[p]} (pkm_supply[u,dist,p,t]) >= min_share[u,dist] * Population * DailyDist[dist];