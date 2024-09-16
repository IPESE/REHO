######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---MOBILITY DEMAND PROXY
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------

param Mobility_demand{p in Period, t in Time[p]} default 0; #km (total for all district?)

# ----------------------------------------- VARIABLES ---------------------------------------

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#-SIMPLE MODEL
# ----------------------------------------

subject to MD_c1{u in UnitsOfType['MobilityDemand'],p in Period,t in Time[p]}:
Units_demand['Mobility',u,p,t] >= Mobility_demand[p,t];  # TODO il faut une somme sur les u ici


subject to MD_c2{u in UnitsOfType['MobilityDemand'],p in Period,t in Time[p]}:
Units_demand['Mobility',u,p,t] <= Units_Mult[u];

subject to MD_c3{u in UnitsOfType['MobilityDemand'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = 0.9*Units_demand['Mobility',u,p,t]; 