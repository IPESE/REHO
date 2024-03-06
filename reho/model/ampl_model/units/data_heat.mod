######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---Data Heat Recovery
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------

param DH_efficiency{u in UnitsOfType['DataHeat']} default 0.96;		# 90-96% of energy is recovered from server
param DH_partload_min{u in UnitsOfType['DataHeat']} default 0.1;
param DH_partload_max{u in UnitsOfType['DataHeat']} default 1;

# ---------------------------------------- CONSTRAINTS ---------------------------------------

# Data flow processed
subject to DH_d1{h in House, u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_supply['Data',u,p,t] = Units_demand['Electricity',u,p,t];


# Heat produced from electricity (thermal output = electrical input * DH_thermal_efficiency)
subject to DH_EB_c1{h in House,u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = DH_efficiency[u]*Units_demand['Electricity',u,p,t]; #kW

subject to DH_c1{h in House,u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Mult[u]*DH_partload_max[u];