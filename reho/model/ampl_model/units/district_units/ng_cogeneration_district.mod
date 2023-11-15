######################################################################################################################

#-Variable list 
# NG_Cogeneration_startup														#-Vars CHP

#-Constraints list
# NG_Cogeneration_EB_c1,NG_Cogeneration_EB_c2,NG_Cogeneration_c1,NG_Cogeneration_c2,								#-Csts CHP (general)
# NG_Cogeneration_c3,															#-Csts CHP (min. buffer size)
# NG_Cogeneration_c4,NG_Cogeneration_c5,NG_Cogeneration_c6,NG_Cogeneration_c7										#-Csts CHP (start-ups)	


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---NG COGENERATION UNIT MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-Static natural gas - fired CHP model including:
#	1. part-load efficiencies
#-References : 
#	[1] V. Vukašinović et al., Review of efficiencies of cogeneration units using [...], International journal of Green Energy, 2016. DOI 10.1080/15435075.2014.962032
#   [2] Viessmann products - Vitowin 300 & Vitobloc 200 (ESS) 
# ----------------------------------------- PARAMETERS ---------------------------------------
#-ENGINE
param NG_Cogeneration_partload_max{u in UnitsOfType['NG_Cogeneration']} default 1;										#- [-]	Viessmann (ESS units, Otto engine)
param NG_Cogeneration_partload_min{u in UnitsOfType['NG_Cogeneration']} default 0;									#- [-]	Viessmann (ESS units, Otto engine)
param NG_Cogeneration_E_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.27;								#- 		Viessmann (ESS units, Otto engine)
param NG_Cogeneration_Q_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.59;								#- 		Viessmann (ESS units, Otto engine) at Tr 50°C

# ---------------------------------------- CONSTRAINTS ---------------------------------------
subject to NG_Cogeneration_EB_c1{u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] 	= NG_Cogeneration_E_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];											#kW

subject to NG_Cogeneration_EB_c2{u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = NG_Cogeneration_Q_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];	#kW

#--Sizing
subject to NG_Cogeneration_c1{u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u]*NG_Cogeneration_partload_max[u];																#kW

subject to NG_Cogeneration_c2{u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] >= Units_Mult[u]*NG_Cogeneration_partload_min[u];																#kW

#-Minimum technical buffer size
#-> Factor (i.e. 0.037) assuming a maximum dT of 35°C over three hours of part-load operation 
#subject to NG_Cogeneration_c3{h in House,ui in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],uj in UnitsOfType['WaterTankSH'] inter UnitsOfHouse[h]}:
#Units_Mult[uj] >= if Th_supply_0[h] > 50 then 0.037*Units_Mult[ui]*(NG_Cogeneration_Q_efficiency_nom[ui]/NG_Cogeneration_E_efficiency_nom[ui]) else 0;					#-	

subject to closed_circuit_dhn1{p in Period,t in Time[p]}:
   Network_supply['Heat',p,t] = 0;

subject to closed_circuit_dhn2{p in Period,t in Time[p]}:
   Network_demand['Heat',p,t] = 0;

#-----------------------------------------------------------------------------------------------------------------------
