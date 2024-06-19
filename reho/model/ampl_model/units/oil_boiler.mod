######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Oil boiler
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param OIL_partload_max{u in UnitsOfType['OIL_Boiler']} default 1;
param OIL_efficiency_max{u in UnitsOfType['OIL_Boiler']} default 0.9;

subject to OIL_energy_balance{h in House, l in LayersOfType['ResourceBalance'], u in UnitsOfType['OIL_Boiler'] inter UnitsOfHouse[h] inter UnitsOfLayer[l],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = OIL_efficiency_max[u]*Units_demand[l,u,p,t];

subject to OIL_c1{h in House,u in UnitsOfType['OIL_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]  <= Units_Mult[u]*OIL_partload_max[u];
