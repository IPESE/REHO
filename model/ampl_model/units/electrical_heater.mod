######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ELECTRIC RESISTIVE HEATER MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static electrical boiler model including:
#	1. part-load efficiency
# ----------------------------------------- PARAMETERS ---------------------------------------
param ELH_partload_min{u in UnitsOfType['ElectricalHeater']} default 0.1;		#-		estimated
param ELH_partload_max{u in UnitsOfType['ElectricalHeater']} default 1;			#-		estimated
param ELH_efficiency_max{u in UnitsOfType['ElectricalHeater']} default 0.99;	#-		estimated

# ----------------------------------------- VARIABLES ---------------------------------------

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-SIMPLE MODEL
# ----------------------------------------
subject to ELH_EB_c1{h in House,u in UnitsOfType['ElectricalHeater'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = ELH_efficiency_max[u]*Units_demand['Electricity',u,p,t]; 	#kW

#-Minimum PartLoad
subject to ELH_c1{h in House,u in UnitsOfType['ElectricalHeater'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Mult[u]*ELH_partload_max[u];							#kW
