######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Natural gas boiler (district)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param BOI_district_efficiency_max{u in UnitsOfType['NG_Boiler']} default 0.9;
param BOI_district_partload_max{u in UnitsOfType['NG_Boiler']} default 1;

subject to BOI_district_energy_balance{u in UnitsOfType['NG_Boiler'] ,p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = BOI_district_efficiency_max[u]*Units_demand["NaturalGas",u,p,t];

subject to BOI_district_partload_max{u in UnitsOfType['NG_Boiler'] ,p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t]  <= Units_Mult[u]*BOI_district_partload_max[u];
