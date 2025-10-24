######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ORC model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------

param ORC_efficiency_max{u in UnitsOfType['ORC_DC_district']} default 0.09;
	#temp 75 source, 14 sink

# ---------------------------------------- CONSTRAINTS ---------------------------------------

subject to ORC_op{u in UnitsOfType['ORC_DC_district'], p in Period, t in Time[p]}:
Units_supply['Electricity', u, p, t] = ORC_efficiency_max[u]* Units_demand['Heat',u,p,t];

subject to ORC_all_the_time{u in UnitsOfType['ORC_DC_district'], v in UnitsOfType['DataHeat'], p in Period, t in Time[p]}:
Units_demand['Heat',u,p,t] =  Units_supply['Heat',v,p,t];

subject to ORC_c1{u in UnitsOfType['ORC_DC_district'] ,p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u];


