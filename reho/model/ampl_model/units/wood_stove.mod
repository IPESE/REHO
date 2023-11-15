######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---Wood stove model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------
param WS_partload_min{u in UnitsOfType['WOOD_Stove']} default 0.2;										#- 	estimated
param WS_partload_max{u in UnitsOfType['WOOD_Stove']} default 1;											#-	estimated
#param WS_efficiency_max{u in UnitsOfType['WOOD_Stove']} default 0.92;									#- 	estimated
#param WS_efficiency_min{u in UnitsOfType['WOOD_Stove']} default 0.80;									#- 	estimated
param WS_efficiency{u in UnitsOfType['WOOD_Stove']} default 0.92;										#- 	estimated

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to WS_EB_c1{h in House, l in LayersOfType['ResourceBalance'], u in UnitsOfType['WOOD_Stove'] inter UnitsOfHouse[h] inter UnitsOfLayer[l],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = WS_efficiency[u]*Units_demand[l,u,p,t];

#-Maximum PartLoad
subject to WS_c1{h in House,u in UnitsOfType['WOOD_Stove'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]  <= Units_Mult[u]*WS_partload_max[u];								#kW
