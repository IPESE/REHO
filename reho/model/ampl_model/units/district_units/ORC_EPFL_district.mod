######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ORC model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------
param ORC_max_0{u in UnitsOfType['ORC_EPFL_district']} default 10;	#-	estimated
param ORC_max{u in UnitsOfType['ORC_EPFL_district'],p in Period,t in Time[p]} default ORC_max_0[u];
param ORC_efficiency_max{u in UnitsOfType['ORC_EPFL_district']} default 0.09;		#temp 75 source, 14 sink							#- 	estimated

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to ORC_EB_c1{u in UnitsOfType['ORC_EPFL_district'] ,p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = ORC_efficiency_max[u]*Units_demand["Heat",u,p,t]; #kW

# Constraint to ensure ORC is running for all periods and times
param ORC_min_operation{u in UnitsOfType['ORC_EPFL_district']} default 4.5;  # Small positive value to ensure operation

subject to ORC_all_the_time{u in UnitsOfType['ORC_EPFL_district'], p in Period, t in Time[p]}:
    Units_supply['Electricity', u, p, t] >= ORC_min_operation[u];

