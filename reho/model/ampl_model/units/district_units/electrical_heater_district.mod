######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Electric resistive heater
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param ELH_partload_max{u in UnitsOfType['ElectricalHeater_Heat']} default 1;
param ELH_efficiency_max{u in UnitsOfType['ElectricalHeater_Heat']} default 0.98;

subject to ELH_energy_balance{u in UnitsOfType['ElectricalHeater_Heat'],p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = ELH_efficiency_max[u]*Units_demand['Electricity',u,p,t];

subject to ELH_c1{u in UnitsOfType['ElectricalHeater_Heat'],p in Period,t in Time[p]}:
 Units_supply['Heat',u,p,t] <= Units_Mult[u]*ELH_partload_max[u];
