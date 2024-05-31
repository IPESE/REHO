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
# ----------------------------------------- VARIABLES ---------------------------------------
var travel_time{p in Period,t in Time[p]} >= 0 ; #pkm

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to travel_time_c1{p in Period,t in Time[p]}:
travel_time[p,t] = sum{u in transport_Units : u != "Public_transport"}(Units_supply['Mobility',u,p,t] / Mode_Speed[u]) +( Network_supply['Mobility',p,t] / dp[p] / Mode_Speed['Public_transport']);


subject to travel_time_c2{p in Period}:
sum {t in Time[p]}(travel_time[p,t]) <= max_travel_time * Population; 




#--------------------------------------------------------------------------------------------------------------------#
#-PUBLIC TRANSPORTS
#--------------------------------------------------------------------------------------------------------------------#
# contraindre Network_supply avec un profil de capacité horaire
#-PARAMETERS
# param transport_public_capacity{p in Period, t in Time[p]} default 150; # pkm : availability of public transport each hour in pkm
param max_share_PT default 0.22; # [1] G 3.3.1.6 : share of trains amounts to ~ 20%
#-VARIABLES

#-CONSTRAINTS

# subject to TP_c1{p in Period, t in Time[p]}:
# Network_supply["Mobility",p,t] /d[p] <= transport_public_capacity[p,t];

subject to TP_maxshare{p in Period}:
sum {t in Time[p]}(Network_supply["Mobility",p,t])/dp[p] <= max_share_PT * Population * DailyDist; 







