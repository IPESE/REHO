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

# set transport_Units := setof{u in UnitsOfType['EV'] union UnitsOfType['Bike']} u;
# set transport_Units := UnitsOfType['EV'] union UnitsOfType['Bike'];
set transport_Units; # TODO : check if dynamic to the rest of the code
set Activities := {"work","leisure","travel"}; 
param Mode_Speed{u in transport_Units} default 37.1; # [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
param Daily_Profile{u in transport_Units,p in Period,t in Time[p]} default 1; # initialized through the function generate_mobility_parameters
# ----------------------------------------- VARIABLES ---------------------------------------
var travel_time >= 0 ;

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to travel_time_c1{ p in Period}:
(sum{u in transport_Units : u != "Public_transport"}(sum {i in Time[p]}(Units_supply['Mobility',u,p,i]) / Mode_Speed[u])  + sum {j in Time[p]}(Network_supply['Mobility',p,j]) / Mode_Speed['Public_transport'] )/ Population <= max_travel_time; 




#--------------------------------------------------------------------------------------------------------------------#
#-PUBLIC TRANSPORTS
#--------------------------------------------------------------------------------------------------------------------#
# contraindre Network_supply avec un profil de capacité horaire
#-PARAMETERS
param transport_public_capacity{p in Period, t in Time[p]} default 15; # pkm : availability of public transport each hour in pkm

#-VARIABLES

#-CONSTRAINTS

subject to TP_c1{p in Period, t in Time[p]}:
Network_demand["Mobility",p,t] <= transport_public_capacity[p,t];
