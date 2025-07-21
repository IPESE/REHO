######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---Data Heat Recovery
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# ----------------------------------------- PARAMETERS ---------------------------------------

param DH_efficiency{u in UnitsOfType['DataHeat']} default 0.96;		# 80-96% of energy is recovered from server, rest is assumed to lost to the server room cooling systems
param DC_heat_recovery{u in UnitsOfType['DataHeat']} default 1; #assumes heat recovery systems are installed in the data centres, so that all heat can be recovered, binary parameter
param PUE{u in UnitsOfType['DataHeat']} default 1.3; # Power Usage Effectiveness, ratio of total building energy usage to the energy used by the IT equipment alone, can vary between 1.1 and 2.0, but is typically around 1.3 for modern data centres
param utilisation_factor{u in UnitsOfType['DataHeat']} default 0.327; # Utilisation factor for data centres, represents the fraction of the total capacity that is actually used, typically around 0.3 to 0.4, 0.327 is taken from the RCP clusters at EPFL
param ORC_efficiency{u in UnitsOfType['DataHeat']} default 0.09; # Efficiency of the ORC system, typically around 9% for low-temperature heat source 75 deg C, 15 deg sink, value calculated from Osmose model
# ---------------------------------------- CONSTRAINTS ---------------------------------------

# Data flow processed
subject to DH_d1{ u in UnitsOfType['DataHeat'], p in Period, t in Time[p]}:
        Units_supply['Data',u,p,t] = Units_demand['Electricity',u,p,t]/ PUE[u]; #kW Units of electricity consumed for IT equipment, based on PUE ratio

subject to DH_d2{ u in UnitsOfType['DataHeat'], p in Period, t in Time[p]}:
       Units_demand['Electricity',u,p,t] = data_EUD['Data',p,t];


# Heat produced from electricity (thermal output = electrical input * DH_thermal_efficiency)
subject to DH_EB_c1{u in UnitsOfType['DataHeat'] ,p in Period,t in Time[p]}:
        Units_supply['Heat',u,p,t] = DC_heat_recovery[u]*DH_efficiency[u]*Units_supply['Data',u,p,t];  #kW


subject to DH_c1{u in UnitsOfType['DataHeat'],p in Period,t in Time[p]}:
        Units_supply['Data',u,p,t]<= utilisation_factor[u]*Units_Mult[u];

