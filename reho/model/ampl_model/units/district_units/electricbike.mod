######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ELECTRIC BIKE BIKE MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Simple mobility model

# [1] Federal office of statistic. (2017). Comportement de la population en matière de transports (841–1500; p. 88).
# [2] https://electrek.co/2020/06/12/how-far-can-an-electric-bicycle-really-go-on-a-charge/ 
# [3] https://www.decathlon.ch/fr/p/velo-ville-longue-distance-500-assistance-electrique-cadre-bas/_/R-p-302285?mc=8526895&c=vert 


# ----------------------------------------- PARAMETERS ---------------------------------------
# param max_speed default 13.3; # pkm per hour [1] Fig G 3.3.1.3 : Vitesse moyenne des utilisateurs des moyens de transport terrestres, en 2015
param max_EBikedistperday default 17; # pkm moyenne mobilité douce : 2.8km per day [1] T 3.3.1.1
param n_EBikesperhab default 1;
param max_n_EBikes := n_EBikesperhab * Population;

# [1] G 3.3.1.6 : share of bikes and walking amounts to ~ 8%


# param max_modal_share default 1; # 8 % de mobilité douce - [1] Fig G 3.3.1.1 : Choix du moyen de transport, en 2015
param tau_relaxation_supply_Ebike default 0.03; # relaxation of the daily profile constraint by 3%. 

# electrical parameters
param EBike_eff_travel default 80;      # km/kWh [2]
param EBike_capacity default 0.5;   # kWh  [3]
param EBike_charging_profile{u in UnitsOfType['EBike'],p in Period,t in Time[p]} default 0.15;
param EBike_eff_ch default 0.9;	# taken from EVs
param EBike_charging_power default 0.07; # kW [3]
param tau_relaxation_demand_EBike default 0.07;  # relaxation of the charging profile constraint by 7%.

# ----------------------------------------- VARIABLES ---------------------------------------
var n_EBikes{u in UnitsOfType['EBike']} integer >= 0; # number 
var coeff_supply_EBike{u in UnitsOfType['EBike'],p in Period } >= 0; # [-]
var coeff_demand_EBike{u in UnitsOfType['EBike'],p in Period } >= 0; # [-]

var EBike_SOC{u in UnitsOfType['EBike'],p in Period,t in Time[p]}  >= 0; # kWh
# ---------------------------------------- CONSTRAINTS ---------------------------------------

# Constraints related to bike usage

subject to ElectricBikes_c2{u in UnitsOfType['EBike'],p in Period}:
sum {i in Time[p]}(Units_supply['Mobility',u,p,i]) <= max_EBikedistperday * n_EBikes[u] ;

subject to ElectricBikes_cb1:
sum{u in UnitsOfType["EBike"]}(n_EBikes[u]) <= max_n_EBikes;

subject to ElectricBikes_cb2{u in UnitsOfType["EBike"]}:
n_EBikes[u] = Units_Mult[u];

subject to ElectricBikes_profile1{u in UnitsOfType['EBike'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] <= coeff_supply_EBike[u,p] * Daily_Profile[u,p,t] * (1+ tau_relaxation_supply_Ebike);

subject to ElectricBikes_profile2{u in UnitsOfType['EBike'],p in Period, t in Time[p]}:
Units_supply['Mobility',u,p,t] >= coeff_supply_EBike[u,p] * Daily_Profile[u,p,t] * (1 - tau_relaxation_supply_Ebike);

subject to ElectricBikes_maxshare{u in UnitsOfType['EBike'],p in PeriodStandard, dist in Distances}:
sum { t in Time[p]} (pkm_supply[u,dist,p,t]) <= max_share[u,dist] * Population * DailyDist[dist];

subject to ElectricBikes_minshare{u in UnitsOfType['EBike'],p in PeriodStandard, dist in Distances}:
sum { t in Time[p]} (pkm_supply[u,dist,p,t]) >= min_share[u,dist] * Population * DailyDist[dist];

# Constraints related to the electric battery (taken from the EVehicle.mod)
subject to EBike_EB_mobility1{u in UnitsOfType['EBike'],p in Period,t in Time[p]}:
Units_supply['Mobility',u,p,t] <= Mode_Speed[u] * n_EBikes[u];

subject to EBike_EB_main{u in UnitsOfType['EBike'],p in PeriodStandard,t in Time[p] diff {first(Time[p])}}:
EBike_SOC[u,p,t] = EBike_SOC[u,p,prev(t,Time[p])] - Units_supply['Mobility',u,p,t] / EBike_eff_travel  + Units_demand['Electricity',u,p,t]*EBike_eff_ch;

subject to EBike_EB_cyclic{u in UnitsOfType['EBike'],p in PeriodStandard,t in Time[p]:t=first(Time[p])}:
EBike_SOC[u,p,t] = EBike_SOC[u,p,last(Time[p])] - Units_supply['Mobility',u,p,t] / EBike_eff_travel  + Units_demand['Electricity',u,p,t]*EBike_eff_ch;

subject to EBike_chargingprofile1{u in UnitsOfType['EBike'],p in PeriodStandard,t in Time[p]}:
Units_demand['Electricity',u,p,t] <= coeff_demand_EBike[u,p] * EBike_charging_profile[u,p,t] * (1 + tau_relaxation_demand_EBike); 

subject to EBike_chargingprofile2{u in UnitsOfType['EBike'],p in PeriodStandard,t in Time[p]}:
Units_demand['Electricity',u,p,t] >= coeff_demand_EBike[u,p] * EBike_charging_profile[u,p,t] * (1 - tau_relaxation_demand_EBike); 


# capacities
subject to EBike_capacityc1{u in UnitsOfType['EBike'],p in PeriodStandard,t in Time[p]}:
EBike_SOC[u,p,t] <= EBike_capacity;