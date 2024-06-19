######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Wood stove
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param WS_efficiency{u in UnitsOfType['WOOD_Stove']} default 0.85;
param WS_partload_max{u in UnitsOfType['WOOD_Stove']} default 1;

subject to WS_energy_balance{h in House, l in LayersOfType['ResourceBalance'], u in UnitsOfType['WOOD_Stove'] inter UnitsOfHouse[h] inter UnitsOfLayer[l],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = WS_efficiency[u]*Units_demand[l,u,p,t];

subject to WS_partload_max{h in House,u in UnitsOfType['WOOD_Stove'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]  <= Units_Mult[u]*WS_partload_max[u];
