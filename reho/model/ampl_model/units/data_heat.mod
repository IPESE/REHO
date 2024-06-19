######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Heat recovery from data center
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param DC_efficiency{u in UnitsOfType['DataHeat']} default 0.96;
param DC_partload_max{u in UnitsOfType['DataHeat']} default 1;

# Data flow processed
subject to DC_data{h in House, u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_supply['Data',u,p,t] = Units_demand['Electricity',u,p,t];

subject to DC_energy_balance{h in House,u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = DC_efficiency[u]*Units_demand['Electricity',u,p,t];

subject to DC_c1{h in House,u in UnitsOfType['DataHeat'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Mult[u]*DC_partload_max[u];
