######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---DEEP MIND-BODY Connection unit model
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static electrical boiler model including:
#	1. part-load efficiency

param DMBC_efficiency_max{u in UnitsOfType['Relaxation']} default 0.99;	#-		estimated

# ----------------------------------------- VARIABLES ---------------------------------------

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-SIMPLE MODEL
# ----------------------------------------
subject to DMBC_EB_c1{h in House,u in UnitsOfType['Relaxation'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = DMBC_efficiency_max[u]*Units_demand['Chakra',u,p,t]; 	#kW

subject to DMBC_c1{h in House,u in UnitsOfType['Relaxation'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Chakra',u,p,t] <= Units_Mult[u] 	#kW