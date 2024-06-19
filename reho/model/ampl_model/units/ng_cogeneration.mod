######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Natural gas cogeneration
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-Static natural gas - fired CHP model including:
#	1. part-load efficiencies
#-References : 
#	[1] V. Vukašinović et al., Review of efficiencies of cogeneration units using [...], International journal of Green Energy, 2016. DOI 10.1080/15435075.2014.962032
#   [2] Viessmann products - Vitowin 300 & Vitobloc 200 (ESS) 

param NG_Cogeneration_partload_max{u in UnitsOfType['NG_Cogeneration']} default 1;
param NG_Cogeneration_partload_min{u in UnitsOfType['NG_Cogeneration']} default 0.5;
param NG_Cogeneration_E_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.27;
param NG_Cogeneration_Q_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.59;

subject to NG_Cogeneration_energy_balance{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] 	= NG_Cogeneration_E_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];

subject to NG_Cogeneration_EB_c2{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = NG_Cogeneration_Q_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];

subject to NG_Cogeneration_c1{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u]*NG_Cogeneration_partload_max[u];

subject to NG_Cogeneration_c2{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] >= Units_Mult[u]*NG_Cogeneration_partload_min[u];

#-Minimum technical buffer size
#-> Factor (i.e. 0.037) assuming a maximum dT of 35°C over three hours of part-load operation 
subject to NG_Cogeneration_c3{h in House,ui in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
Units_Mult[uj] >= if Th_supply_0[h] > 50 then 0.037*Units_Mult[ui]*(NG_Cogeneration_Q_efficiency_nom[ui]/NG_Cogeneration_E_efficiency_nom[ui]) else 0;					#-	
