######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---NG BOILER MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static natural gas - fired boiler model including:
#	1. part-load efficiency
# ----------------------------------------- PARAMETERS ---------------------------------------
param BOI_partload_min{u in UnitsOfType['NG_Boiler']} default 0.2;										#- 	estimated
param BOI_partload_max{u in UnitsOfType['NG_Boiler']} default 1;										#-	estimated
param BOI_efficiency_max{u in UnitsOfType['NG_Boiler']} default 0.95;									#- 	estimated
param BOI_efficiency_min{u in UnitsOfType['NG_Boiler']} default 0.80;									#- 	estimated
param BOI_efficiency_slope{u in UnitsOfType['NG_Boiler']} :=
	if BOI_partload_min[u] < 1 then 
		(BOI_efficiency_max[u]*BOI_partload_max[u] - BOI_efficiency_min[u]*BOI_partload_min[u])/(BOI_partload_max[u] - BOI_partload_min[u]) 
	else 
		0
	;																								#-	computed

subject to BOI_EB_c1{h in House, l in LayersOfType['ResourceBalance'], u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h] inter UnitsOfLayer[l],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = BOI_efficiency_max[u]*Units_demand[l,u,p,t];	

#-Minimum PartLoad
subject to BOI_c1{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]  <= Units_Mult[u]*BOI_partload_max[u];								#kW

#-ADVANCED MODEL (not used)
# ----------------------------------------
# subject to Conversion_BO_Partload_c1{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = BO_efficiency_min[u]*(BO_partload_min[u]*Units_Use_Mult_t[u,p,t]/BO_efficiency_min[u]) 
																					# + BO_efficiency_slope[u]*BO_NG_demand_d[u,p,t];			#kW
																					
# subject to Conversion_BO_Partload_c2{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# Units_demand['NaturalGas',u,p,t] = BO_NG_demand_d[u,p,t] + BO_partload_min[u]*Units_Use_Mult_t[u,p,t]/BO_efficiency_min[u];			#kW

#-Minimum PartLoad
# subject to Conversion_Boiler_Max_out{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Use_Mult_t[u,p,t]*BO_partload_max[u];					#kW

# subject to Conversion_Boiler_Min_in{h in House,u in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
# sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] >= Units_Use_Mult_t[u,p,t]*BO_partload_min[u];					#kW

#-----------------------------------------------------------------------------------------------------------------------
