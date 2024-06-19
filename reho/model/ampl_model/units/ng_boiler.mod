######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Natural gas boiler
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param BOI_efficiency_max{u in UnitsOfType['NG_Boiler']} default 0.95;
param BOI_partload_max{u in UnitsOfType['NG_Boiler']} default 1;

subject to BOI_energy_balance{h in House, l in LayersOfType['ResourceBalance'], u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h] inter UnitsOfLayer[l],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = BOI_efficiency_max[u]*Units_demand[l,u,p,t];	

subject to BOI_partload_max{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]  <= Units_Mult[u]*BOI_partload_max[u];


#-Advanced model with part-load efficiencies

# param BOI_partload_min{u in UnitsOfType['NG_Boiler']} default 0.2;
# param BOI_partload_max{u in UnitsOfType['NG_Boiler']} default 1;
# param BOI_efficiency_max{u in UnitsOfType['NG_Boiler']} default 0.95;
# param BOI_efficiency_min{u in UnitsOfType['NG_Boiler']} default 0.80;
# param BOI_efficiency_slope{u in UnitsOfType['NG_Boiler']} :=
# 	if BOI_partload_min[u] < 1 then
# 		(BOI_efficiency_max[u]*BOI_partload_max[u] - BOI_efficiency_min[u]*BOI_partload_min[u])/(BOI_partload_max[u] - BOI_partload_min[u])
# 	else
# 		0
# 	;

# subject to Conversion_BO_Partload_c1{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = BO_efficiency_min[u]*(BO_partload_min[u]*Units_Use_Mult_t[u,p,t]/BO_efficiency_min[u]) 
																					# + BO_efficiency_slope[u]*BO_NG_demand_d[u,p,t];
																					
# subject to Conversion_BO_Partload_c2{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# Units_demand['NaturalGas',u,p,t] = BO_NG_demand_d[u,p,t] + BO_partload_min[u]*Units_Use_Mult_t[u,p,t]/BO_efficiency_min[u];

#-Minimum PartLoad
# subject to Conversion_Boiler_Max_out{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Use_Mult_t[u,p,t]*BO_partload_max[u];

# subject to Conversion_Boiler_Min_in{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] >= Units_Use_Mult_t[u,p,t]*BO_partload_min[u];
