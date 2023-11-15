######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---NG boiler model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------
param NG_partload_max{u in UnitsOfType['NG_Boiler']} default 1;										#-	estimated
param NG_efficiency_max{u in UnitsOfType['NG_Boiler']} default 0.9;									#- 	estimated

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to NG_EB_c1{u in UnitsOfType['NG_Boiler'] ,p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = NG_efficiency_max[u]*Units_demand["NaturalGas",u,p,t];

#-Maximum PartLoad
subject to NG_c1{u in UnitsOfType['NG_Boiler'] ,p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t]  <= Units_Mult[u]*NG_partload_max[u];								#kW
