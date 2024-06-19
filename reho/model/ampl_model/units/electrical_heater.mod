######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Electric resistive heater
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param ELH_partload_max{u in UnitsOfType['ElectricalHeater']} default 1;
param ELH_efficiency_max{u in UnitsOfType['ElectricalHeater']} default 0.98;

subject to ELH_energy_balance{h in House,u in UnitsOfType['ElectricalHeater'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] = ELH_efficiency_max[u]*Units_demand['Electricity',u,p,t];

subject to ELH_partload_max{h in House,u in UnitsOfType['ElectricalHeater'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t] <= Units_Mult[u]*ELH_partload_max[u];
