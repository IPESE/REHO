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

param max_travel_time default 1.3; # 3 hours 

# set transport_Units := setof{u in UnitsOfType['EV'] union UnitsOfType['Bike']} u;
# set transport_Units := UnitsOfType['EV'] union UnitsOfType['Bike'];
set transport_Units default {'Bike_district','EV_district','ICE_district'}; # TODO : not dynamic to the rest of the code, à améliorer
param Mode_Speed{transport_Units};
let Mode_Speed['EV_district'] := 37.1; # km/h [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
let Mode_Speed['ICE_district'] := 37.1; # km/h
let Mode_Speed['Bike_district'] := 13.3;
# ----------------------------------------- VARIABLES ---------------------------------------
var travel_time >= 0 ;

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to travel_time_c1{ p in Period}:
sum{u in transport_Units}(sum {i in Time[p]}(Units_supply['Mobility',u,p,i]) / Mode_Speed[u]) / Population <= max_travel_time; 




# Transport Public
# contraindre Network_supply avec un profil de capacité horirea