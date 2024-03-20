######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---OVERARCHING MOBILITY MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model
# Declare generic parameters and constraints valid for the transport sector


# ----------------------------------------- PARAMETERS ---------------------------------------
param Population default 7.5; # will multiply the domestic demand ? 

param max_travel_time default 1.3; # 3 hours 

set test default {'Bike_district','EV_district'};
param Mode_Speed{test};
let Mode_Speed['EV_district'] := 37.1; # km/h

let Mode_Speed['Bike_district'] := 13.3;
# ----------------------------------------- VARIABLES ---------------------------------------
var travel_time >= 0 ;

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to travel_time_c1{ p in Period}:
sum{u in test}(sum {i in Time[p]}(Units_supply['Mobility',u,p,i]) / Mode_Speed[u]) / Population <= max_travel_time; 