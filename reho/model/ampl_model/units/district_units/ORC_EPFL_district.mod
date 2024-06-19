######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ORC model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------
param ORC_max{u in UnitsOfType['ORC_EPFL_district']} default 10;										#-	estimated
param ORC_efficiency_max{u in UnitsOfType['ORC_EPFL_district']} default 0.09;		#temp 75 source, 14 sink							#- 	estimated

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to ORC_EB_c1{u in UnitsOfType['ORC_EPFL_district'] ,p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = ORC_efficiency_max[u]*Units_demand["Heat",u,p,t];

#-Maximum PartLoad
subject to ORC_c1{u in UnitsOfType['ORC_EPFL_district'] ,p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t]  <= Units_Mult[u]*ORC_max[u];								#kW
